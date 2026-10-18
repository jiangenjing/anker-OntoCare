import json,importlib.util
from pathlib import Path
D=Path(__file__).parent
spec=importlib.util.spec_from_file_location('runner',D/'ontocare-benchmark-runner.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
p=D/'benchmark-results.json';data=json.loads(p.read_text());extra=json.loads((D/'persona-results.json').read_text())
old={(x['mode'],x['id'],x['repeat']) for x in data['results']}
data['results'] += [x for x in extra['results'] if (x['mode'],x['id'],x['repeat']) not in old]
data['results'].sort(key=lambda x:(x['mode'],x['id'],x['repeat']))
data['metadata']=json.loads((D/'ontocare-user-test-cases.json').read_text())['metadata'];data['summary']=r.aggregate(data['results']);data['config']['supplemental_persona_run']=extra['config'];data['generated_at']=extra['generated_at']
p.write_text(json.dumps(data,ensure_ascii=False));print(json.dumps(data['summary']))
