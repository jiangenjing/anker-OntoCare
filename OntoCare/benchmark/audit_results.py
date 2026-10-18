"""Re-score unchanged observations after reviewing the evaluator, not the application.
Preserves earlier scores and judge assessments. No customer replies are regenerated.
"""
import json,hashlib,importlib.util,datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
D=Path(__file__).parent
spec=importlib.util.spec_from_file_location('runner',D/'ontocare-benchmark-runner.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);r.load_env()
p=D/'benchmark-results.json';data=json.loads(p.read_text());case_map={c['id']:c for c in r.cases()}
audit={'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'changes':['U063 order number equality is case-insensitive; original source card uses Anker002, internal state ANKER002.','Judge receives explicit task success contract and verified authorization rules, preventing correct refusal/clarification from being penalized for missing policy context.','No-reply HTTP boundary / crashed cases have no semantic answer to judge and are NOT_APPLICABLE, not zero-quality fabricated scores.'],'prior_assessments':[{'id':x['id'],'mode':x['mode'],'repeat':x['repeat'],'checks':x['checks'],'judge':x['judge']} for x in data['results'] if x['repeat']==1 or x['id']=='U063']}
(D/'evaluator-audit-before.json').write_text(json.dumps(audit,ensure_ascii=False))
for row in data['results']:row['checks']=r.check_case(case_map[row['id']],row['trajectory'],row['final_state'],row['extras']);row['status']='PASS' if all(c['passed'] for c in row['checks']) else 'FAIL'
selected=[x for x in data['results'] if x['mode']=='online' and x['repeat']==1]
for x in selected:
 if not any(t['response'].get('reply') for t in x['trajectory']):x['judge']={'status':'NOT_APPLICABLE'}
selected=[x for x in selected if any(t['response'].get('reply') for t in x['trajectory'])]
with ThreadPoolExecutor(max_workers=8) as pool:
 futures={pool.submit(r.judge,case_map[x['id']],x['trajectory'],x['extras']):x for x in selected}
 for i,f in enumerate(as_completed(futures),1):futures[f]['judge']=f.result();print(i, len(selected),futures[f]['id'],futures[f]['judge']['status'],flush=True)
data['summary']=r.aggregate(data['results']);data['config']['scoring_runner_sha256']=hashlib.sha256((D/'ontocare-benchmark-runner.py').read_bytes()).hexdigest();data['config']['evaluator_audit']='evaluator-audit-before.json; immutable application observations; corrected oracle; first-trial judge re-run once'
data['generated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();p.write_text(json.dumps(data,ensure_ascii=False))
print(json.dumps(data['summary']),flush=True)
