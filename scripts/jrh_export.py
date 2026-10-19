"""Offline, loss-aware JRH interchange export. Never imports JRH or a model client."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from analyze_responses import parse_prediction


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def key(row):
    values = row.get('example_id', row.get('case_id')), row.get('condition')
    return tuple(v if isinstance(v,str) else None for v in values)


def convert(plans, responses, repeat_id, ledger):
    lookup = {}
    for p in plans:
        k = key(p)
        if None in k or k in lookup or p['repeat_id'] != repeat_id:
            raise ValueError('Duplicate plan or inconsistent repeat')
        if not all(p.get(f) is not None for f in ('source_id','case_id','condition','linkage_state','representation','prompt_sha256')):
            raise ValueError('Incomplete plan metadata')
        lookup[k] = p
    counts = Counter(key(r) for r in responses if isinstance(r,dict))
    rows = []
    for line, raw in enumerate(responses, 1):
        r = raw if isinstance(raw, dict) else {}
        k = key(r); p = lookup.get(k, {})
        status = 'malformed_record'; score = None
        parse_error = None
        if isinstance(raw,dict):
            if r.get('status') != 'ok':
                status = 'transport_error' if r.get('status') else 'malformed_record'
            else:
                try:
                    score = parse_prediction(r.get('response_text')); status = 'ok'
                except (ValueError,TypeError) as e:
                    status = 'parse_error'; parse_error = str(e)
            if p and r.get('prompt_sha256') != p['prompt_sha256']:
                status = 'prompt_mismatch'; score = None
        rows.append(dict(source_id=p.get('source_id'), case_id=k[0],
            linkage_state=p.get('linkage_state'), representation=p.get('representation'),
            repeat_id=repeat_id, condition=k[1], prompt_sha256=p.get('prompt_sha256'),
            observed_prompt_sha256=r.get('prompt_sha256'),
            planned=bool(p), duplicate_response=counts[k]>1 if isinstance(raw,dict) else False,
            status=status, transport_status=r.get('status'), autograder_score=score,
            validation_score=None, reference_basis='no overall-risk gold supplied',
            ledger=ledger, ledger_line=line, attempt=r.get('attempt'),
            returned_model=r.get('returned_model'), request_id=r.get('request_id'),
            parse_error=parse_error, raw_record=raw))
    for k,p in lookup.items():
        if counts[k] == 0:
            rows.append(dict(p, planned=True, duplicate_response=False, status='missing',
                transport_status=None, autograder_score=None, validation_score=None,
                reference_basis='no overall-risk gold supplied', ledger=ledger,
                ledger_line=None, attempt=None, raw_record=None))
    for n,r in enumerate(rows,1):
        r['perturbed_idx'] = f'block-{repeat_id}:row-{n}'
    return rows


def read_rows(path):
    rows=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        try: rows.append(json.loads(line))
        except ValueError: rows.append(line)
    return rows


def export(manifest_path, output):
    manifest_path=Path(manifest_path).resolve(); output=Path(output)
    if output.exists(): raise FileExistsError('Export destination must be new')
    spec=json.loads(manifest_path.read_text(encoding='utf-8'))
    rows=[]; inputs=[]; repeats=set()
    for block in spec['blocks']:
        repeat=block['repeat_id']
        if type(repeat) is not int or repeat<1 or repeat in repeats:
            raise ValueError('Unique positive repeat_id required')
        repeats.add(repeat)
        path=(manifest_path.parent/block['path']).resolve()
        if not path.exists():
            if block['sha256'] is not None: raise ValueError('Expected ledger absent')
            responses=[]; actual=None
        else:
            actual=sha(path)
            if actual != block['sha256']: raise ValueError('Ledger hash mismatch')
            responses=read_rows(path)
        inputs.append(dict(path=str(path),sha256=actual))
        rows.extend(convert(block['plans'],responses,repeat,block['path']))
    output.mkdir(parents=True,exist_ok=False)
    (output/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    # Full record stays in JSONL. CSV is a scalar view with explicit nulls.
    fields=sorted(set().union(*(r.keys() for r in rows))-{'raw_record'}) if rows else []
    with (output/'records.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k:'null' if r.get(k) is None else r[k] for k in fields})
    (output/'plan.json').write_bytes(manifest_path.read_bytes())
    summary=dict(schema_version=1, format='JRH interchange; not direct EvalMetrics input',
        upstream_commit='82ef3aed74950ba03eadcdb087743251196355a3',
        planned_slots=sum(len(b['plans']) for b in spec['blocks']),
        observed_records=sum(r['ledger_line'] is not None for r in rows),
        exported_rows=len(rows), statuses=dict(Counter(r['status'] for r in rows)),
        duplicate_response_rows=sum(r['duplicate_response'] for r in rows),
        unexpected_records=sum(not r['planned'] for r in rows),
        source_count=len({r['source_id'] for r in rows if r['source_id'] is not None}),
        plan_sha256=sha(manifest_path), input_ledgers=inputs,
        exporter_sha256=sha(__file__), parser_sha256=sha(Path(__file__).with_name('analyze_responses.py')),
        artifact_sha256={name:sha(output/name) for name in ['records.jsonl','records.csv','plan.json']},
        new_api_calls=0, eligible_for_default_jrh_metrics=False,
        limits=['No overall-risk gold inferred from linkage state.',
                'Repeated calls are not independent source scenes.',
                'Duplicates and unexpected records require explicit adjudication; no attempt selected.',
                'Missing means no matching ledger row, not proof that no remote request occurred.',
                'Contains model outputs; do not send to blinded reviewers.'])
    (output/'manifest.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True); p.add_argument('--output',required=True)
    args=p.parse_args(); result=export(args.manifest,args.output)
    print(json.dumps({k:result[k] for k in ['planned_slots','observed_records','statuses','new_api_calls']}))


if __name__=='__main__': main()
