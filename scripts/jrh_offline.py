"""Read-only JRH cache interoperability and conservative statistical admission."""
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
import runpy
import socket
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from analyze_responses import parse_prediction

COMMIT='82ef3aed74950ba03eadcdb087743251196355a3'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def slot(r): return (r.get('case_id'),r.get('condition'),r.get('repeat_id'))


def qualify(rows,plans):
    lookup={slot(p):p for p in plans}
    if len(lookup)!=len(plans): raise ValueError('Duplicate plan slot')
    counts=Counter(slot(r) for r in rows)
    if set(lookup)-set(counts): raise ValueError('Export omits planned slots')
    result=[]
    for row in rows:
        reasons=[]; k=slot(row); p=lookup.get(k)
        if p is None: reasons.append('unexpected_slot')
        if counts[k]>1: reasons.append('duplicate_slot')
        if row.get('duplicate_response') is not False: reasons.append('duplicate_flag')
        if row.get('planned') is not True: reasons.append('not_planned')
        if row.get('status')!='ok': reasons.append('status_not_ok')
        if p and any(row.get(f)!=p.get(f) for f in ('source_id','linkage_state','representation','prompt_sha256')):
            reasons.append('plan_metadata_mismatch')
        score=row.get('autograder_score')
        if type(score) is not int or not 1<=score<=5: reasons.append('invalid_score')
        raw=row.get('raw_record')
        if not isinstance(raw,dict) or raw.get('status')!='ok': reasons.append('raw_not_ok')
        else:
            if (raw.get('example_id'),raw.get('condition'))!=k[:2]: reasons.append('raw_id_mismatch')
            if not p or raw.get('prompt_sha256')!=p.get('prompt_sha256'): reasons.append('raw_prompt_mismatch')
            try:
                if parse_prediction(raw.get('response_text'))!=score: reasons.append('raw_score_mismatch')
            except (ValueError,TypeError): reasons.append('raw_parse_error')
        result.append(dict(row,eligible=not reasons,exclusion_reasons=reasons))
    return result


@contextmanager
def guarded_evaluator(upstream):
    """No SDK import; every model/score path and socket connection fails closed."""
    def deny(*a,**k): raise RuntimeError('OFFLINE_ONLY: scoring/network forbidden')
    core=ModuleType('core'); schemas=ModuleType('schemas')
    for name in ['LLMClient','get_response_schema','threaded_executor']: setattr(core,name,deny)
    core.console=SimpleNamespace(print=lambda *a,**k:None)
    schemas.EvaluationConfig=object; schemas.LLMClientConfig=object
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
        with patch.dict(sys.modules,{'core':core,'schemas':schemas}):
            cls=runpy.run_path(str(upstream))['Evaluator']
        for name in ['_grade_single','_grade_multi_judge','grade_original_preprocess','grade_synthetic_data']:
            setattr(cls,name,deny)
        yield cls


def run(bundle,output,project):
    import pandas as pd
    bundle=Path(bundle).resolve(); output=Path(output).resolve(); project=Path(project).resolve()
    if output.exists(): raise FileExistsError('Use new output directory')
    manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
    for name in ['records.jsonl','records.csv','plan.json']:
        if sha(bundle/name)!=manifest['artifact_sha256'][name]: raise ValueError('Bundle hash mismatch: '+name)
    rows=[json.loads(s) for s in (bundle/'records.jsonl').read_text(encoding='utf-8').splitlines()]
    plan=json.loads((bundle/'plan.json').read_text(encoding='utf-8'))
    plans=[]
    for block in plan['blocks']:
        if any(p['repeat_id']!=block['repeat_id'] for p in block['plans']): raise ValueError('Repeat mismatch')
        plans.extend(block['plans'])
    qualified=qualify(rows,plans)
    with (bundle/'records.csv').open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; cells=list(reader)
    expected=[{k:'null' if r.get(k) is None else str(r[k]) for k in fields} for r in rows]
    if cells!=expected: raise ValueError('CSV/JSONL mismatch')
    if not {'perturbed_idx','status','autograder_score'}.issubset(fields): raise ValueError('Missing required CSV columns')
    if len({r['perturbed_idx'] for r in rows})!=len(rows): raise ValueError('Duplicate row identifier')
    upstream=project/'vendor/jrh/evaluator.py'
    if sha(upstream)!='f3c4fb85d8d6e5de9fdaa1f6f81711a97fee067ec332788df98c27dd37670bd9': raise ValueError('Unverified upstream code')
    frame=pd.read_csv(bundle/'records.csv')
    output.mkdir(parents=True,exist_ok=False)
    cache=output/'offline_results_offline_stub.csv'
    frame.to_csv(cache,index=True)
    with guarded_evaluator(upstream) as cls:
        config=SimpleNamespace(autograder_model_config=SimpleNamespace(model='offline/stub'),
            output_file_format='csv',output_dir=output,overwrite_results=False)
        loaded=cls(config)._grade_single_judge('offline',frame[['perturbed_idx']])['single_judge']
        pd.testing.assert_frame_equal(loaded.reset_index(drop=True),frame.reset_index(drop=True))
    def save(name,data):
        (output/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data),encoding='utf-8')
    save('all-records.jsonl',qualified)
    eligible=[r for r in qualified if r['eligible']]; excluded=[r for r in qualified if not r['eligible']]
    save('eligible-records.jsonl',eligible);save('excluded-records.jsonl',excluded)
    groups={}
    for r in eligible:
        k=(r['source_id'],r['linkage_state'],r['representation'],r['condition'])
        groups.setdefault(k,[]).append(r)
    summary=dict(total_rows=len(rows),planned_slots=len(plans),eligible_rows=len(eligible),excluded_rows=len(excluded),
        eligible_sources=len({r['source_id'] for r in eligible}),
        exclusion_reasons=dict(Counter(reason for r in excluded for reason in r['exclusion_reasons'])),
        descriptive_groups=[dict(source_id=k[0],linkage_state=k[1],representation=k[2],condition=k[3],
            observed_repeats=[r['repeat_id'] for r in vs],
            risk_counts={str(i):sum(r['autograder_score']==i for r in vs) for i in range(1,6)}) for k,vs in sorted(groups.items())],
        upstream_commit=COMMIT,upstream_sha256=sha(upstream),script_sha256=sha(__file__),
        input_manifest_sha256=sha(bundle/'manifest.json'),new_model_api_calls=0,
        limits=['Eligibility is record integrity, not semantic validation or independent samples.',
                'No accuracy, significance or default JRH metrics; risk gold remains absent.',
                'Python guards are for this pinned path, not an OS sandbox for arbitrary code.'])
    summary['output_sha256']={n:sha(output/n) for n in ['all-records.jsonl','eligible-records.jsonl','excluded-records.jsonl','offline_results_offline_stub.csv']}
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True);p.add_argument('--output',required=True)
    p.add_argument('--project',default=str(Path(__file__).resolve().parents[1]))
    a=p.parse_args();r=run(a.bundle,a.output,a.project)
    print(json.dumps({k:r[k] for k in ['total_rows','eligible_rows','excluded_rows','new_model_api_calls']}))
