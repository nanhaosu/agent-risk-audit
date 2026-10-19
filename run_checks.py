"""Verify package integrity, unit contracts and offline cache guards."""
import hashlib,json,pathlib,socket,sys,tempfile,unittest
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parent
manifest=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'))
for name,expected in manifest['files'].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
        raise RuntimeError('Package hash mismatch: '+name)
sys.path.insert(0,str(ROOT/'scripts'))
from jrh_offline import run,guarded_evaluator,COMMIT
import pandas as pd
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner().run(suite)
if not result.wasSuccessful():raise SystemExit(1)
with tempfile.TemporaryDirectory() as tmp:
    out=pathlib.Path(tmp)/'run'
    summary=run(ROOT/'fixture',out,ROOT)
    assert (summary['total_rows'],summary['eligible_rows'],summary['excluded_rows'])==(10,1,9)
    assert sum(sum(g['risk_counts'].values()) for g in summary['descriptive_groups'])==1
    try:run(ROOT/'fixture',out,ROOT)
    except FileExistsError:pass
    else:raise AssertionError('Overwrite accepted')
    upstream=ROOT/'vendor/jrh/evaluator.py'
    with guarded_evaluator(upstream) as cls:
        e=cls(SimpleNamespace(autograder_model_config=SimpleNamespace(model='offline/stub'),output_file_format='csv',output_dir=out,overwrite_results=False))
        probes=[lambda:e._grade_single_judge('offline',pd.DataFrame({'perturbed_idx':['new']})),lambda:e._grade_single_judge('stochastic_stability',pd.DataFrame()),lambda:e.grade_synthetic_data('offline',pd.DataFrame()),lambda:socket.create_connection(('127.0.0.1',9))]
        for probe in probes:
            try:probe()
            except RuntimeError as exc:
                if 'OFFLINE_ONLY' not in str(exc):raise
            else:raise AssertionError('Guard failed')
print(json.dumps({'unit_tests':result.testsRun,'synthetic_rows':10,'eligible':1,'excluded':9,'blocked_probes':4,'new_model_api_calls':0}))
