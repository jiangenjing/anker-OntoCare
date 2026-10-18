"""Isolated red/blue runner. Historical benchmark records and contracts remain intact."""
import copy,hashlib,importlib.util,json,os,tempfile,uuid
from pathlib import Path
from datetime import date,datetime,timezone
from unittest.mock import patch
from benchmark.agents import blue_team,judge
from benchmark.agents.red_team import RedTeam
from benchmark.orchestrator.chaos import inject
from benchmark.config.prompts import PROMPT_VERSION
ROOT=Path(__file__).resolve().parents[2]

def legacy():
 spec=importlib.util.spec_from_file_location('ontocare_legacy_runner',ROOT/'benchmark/ontocare-benchmark-runner.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def load_data():
 engine=legacy();return engine.cases(),json.loads((ROOT/'benchmark/ontocare-persona-vectors.json').read_text())['personas']

def sources_for(m,trajectory):
 ids={s['id'] for t in trajectory for s in t['response'].get('citations',[])};sources=[]
 with m.app.test_client() as client:
  for ident in sorted(ids):
   r=client.get('/api/sources/'+ident)
   if r.status_code==200:sources.append({'id':ident,'content':m.qa.SOURCES.get(ident) or r.get_json(silent=True) or r.get_data(as_text=True)[:16000]})
 return sources

def historical_trace(case,row):
 turns=[]
 for i,t in enumerate(row.get('trajectory',[]),1):
  d=t.get('response',{});trace=d.get('trace',{})
  turns.append({'turn':i,'red_team':{'input':t.get('input',''),'state_change':None,'trigger':'历史记录未逐轮保存'},'blue_team':{'reply':d.get('reply',''),'trace':trace,'citations':d.get('citations',[]),'events':[e for e in t.get('events',[]) if e.get('type')=='progress'],'ontology':d.get('followups',{}).get('ontology'),'latency_ms':t.get('latency_ms'),'status':t.get('status')},'judge':{'semantic_status':'NOT_MEASURED_PER_TURN','faithfulness':None,'tone':None,'action_legality':None}})
 failed=[c for c in row.get('checks',[]) if not c.get('passed')]
 return {'case_id':case['id'],'case_name':case.get('title',case['id']),'source':case.get('ground_truth_source',''),'source_refs':case.get('ground_truth_refs',[]),'persona':case.get('persona_id'),'turns':turns,'final_verdict':{'status':row['status'],'severity':'blocker' if any(c.get('severity')=='P0' for c in failed) else 'general' if failed else 'none','checks':row.get('checks',[]),'reason':'; '.join(c['name'] for c in failed),'suggestion':'按失败断言复核来源与处理规则，修改后重跑；手动标记不改变测试成绩。' if failed else '保留轨迹作为回归样本。'},'final_state':row.get('final_state',{}),'trajectory_judge':row.get('judge',{}),'provenance':'recorded_historical_trial','mode':row.get('mode'),'repeat':row.get('repeat')}

def dynamic_trial(engine,case,persona,config,repeat):
 import app as m
 m.SESSIONS.clear();m.LLM_KEY=os.getenv('LLM_API_KEY','') if config['mode']=='online' else '';m.LLM_MODEL=os.getenv('LLM_MODEL','');m.LLM_BASE=os.getenv('LLM_BASE_URL',m.LLM_BASE);m.GROUNDED_MODE=True
 session='dynamic-'+uuid.uuid4().hex;red=RedTeam(persona,config['max_turns'],config['red_mode'],malicious=False)
 # Dynamic dialogue uses the exact real complaint; fixed adversarial fixtures use the legacy runner.
 before=engine.digest(m.ORDERS);trajectory=[];turns=[];counter={'fault_hits':0};reason='turn_budget';event=red.first()
 class Clock(date):
  @classmethod
  def today(cls):return date.fromisoformat(case['as_of_date'])
 with tempfile.TemporaryDirectory(prefix='ontocare-redblue-') as temp,patch.object(m,'date',Clock),patch.object(m.handoffs,'ROOT',Path(temp)):
  for n in range(1,red.budget+1):
   hits_before=counter['fault_hits']
   with inject(m,config.get('fault'),counter):t=blue_team.send(m,session,event['input'])
   trajectory.append(t);sources=sources_for(m,trajectory)
   review=judge.evaluate(t,case,sources,{x.upper() for x in m.ORDERS},config['judge'],conversation=trajectory)
   d=t['response'];trace=d.get('trace',{})
   safety=trace.get('answer_route')=='HUMAN_REVIEW' and bool(m.re.search(m.qa.RISK,event['input'],m.re.I))
   turns.append({'turn':n,'red_team':event,'blue_team':{'reply':d.get('reply',''),'trace':trace,'citations':d.get('citations',[]),'events':[e for e in t.get('events',[]) if e.get('type')=='progress'],'ontology':d.get('followups',{}).get('ontology'),'status':t['status'],'latency_ms':t['latency_ms'],'fault_hits':counter['fault_hits']-hits_before,'safety_escalated':safety,'safety_meaning':'Safety review advised, not a connected specialist or executed transfer'},'judge':review})
   if safety:reason='safety_review_requested';break
   if t['status']!=200:reason='blue_error';break
   if review['goal_achieved']:reason='goal_achieved_estimate';break
   if n<red.budget:event=red.next(trajectory,sources)
  extras={'order_unchanged':engine.digest(m.ORDERS)==before,'resolvable_ids':[x['id'] for x in sources],'retrieved_sources':sources,**counter}
  checks=engine.check_case(case,trajectory,trajectory[-1]['state'],extras)
  for n,t in enumerate(turns,1):checks += [{**c,'name':f'turn_{n}:'+c['name']} for c in t['judge']['checks']]
  if config.get('fault'):
   checks += [{'name':'fault_injection_hit','passed':counter['fault_hits']>0,'actual':counter['fault_hits'],'severity':'P1'}]
   checks += [{'name':f'turn_{n}:degraded_reason','passed':bool(t['blue_team']['trace'].get('degraded_reason')),'severity':'P1'} for n,t in enumerate(turns,1) if t['blue_team']['fault_hits']]
 failed=[c for c in checks if not c['passed']]
 unavailable=config['judge'] and any(t['judge']['semantic_status']!='ESTIMATE' for t in turns)
 semantic_failed=any(t['judge'].get('semantic_action_legality')=='FAIL' or (t['judge'].get('faithfulness') is not None and t['judge']['faithfulness']<1) for t in turns)
 status='FAIL' if failed or semantic_failed else 'REVIEW_REQUIRED' if unavailable else 'PASS'
 # State-only assertions are absent for some Persona probes; do not invent a terminal verdict.
 state_checks=[c for c in checks if c['name'].startswith(('pn','trace:','action_boundary','handoff_complete'))]
 for t in turns:t['judge']['final_state_match']=None
 if turns:turns[-1]['judge']['final_state_match']=all(c['passed'] for c in state_checks) if state_checks else None
 trace={'case_id':case['id'],'case_name':case.get('title',case['id']),'persona':persona['id']+' '+persona['name'],'source':persona['ground_truth_source'],'source_refs':case['ground_truth_refs'],'turns':turns,'final_state':trajectory[-1]['state'],'stop_reason':reason,'fault':config.get('fault'),'fault_hits':counter['fault_hits'],'final_verdict':{'status':status,'severity':'blocker' if any(c.get('severity')=='P0' for c in failed) else 'general' if status=='FAIL' else 'none','checks':checks,'reason':'; '.join(c['name'] for c in failed) or ('语义检查不通过' if semantic_failed else '语义评审不可用，待复核' if unavailable else '已执行的检查通过；未测量项目保持未测'),'suggestion':'核对失败断言和原始证据，再修改处理规则并复测。' if status!='PASS' else '保留本轮证据用于后续回归。'},'mode':config['mode'],'repeat':repeat,'provenance':'isolated_dynamic_persona_run','prompt_version':PROMPT_VERSION}
 return trace

def run(config,output):
 engine=legacy();engine.load_env();cases,personas=load_data();by_id={c['id']:c for c in cases};by_persona={p['id']:p for p in personas}
 output=Path(output);(output/'traces').mkdir(parents=True,exist_ok=True)
 result={'config':config,'prompt_version':PROMPT_VERSION,'created_at':datetime.now(timezone.utc).isoformat(),'results':[],'historical_comparison':'Separate experiment; do not merge with frozen pass^k results.','source_snapshot_sha256':hashlib.sha256((ROOT/'evaluation/source-snapshot.json').read_bytes()).hexdigest()}
 def save():
  path=output/'benchmark_results.json';temp=path.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2));temp.replace(path)
 for ident in config['case_ids']:
  c=copy.deepcopy(by_id[ident])
  for repeat in range(1,config['repeats']+1):
   if c.get('persona_probe'):trace=dynamic_trial(engine,c,by_persona[c['persona_id']],config,repeat)
   else:
    if config.get('fault'):c['fault_injection']=config['fault']
    record=engine.run_trial((c,config['mode'],repeat,config['judge']));trace=historical_trace(c,record);trace['provenance']='isolated_fixed_fixture_run'
   name=f'{ident}-{repeat}.json';(output/'traces'/name).write_text(json.dumps(trace,ensure_ascii=False,indent=2))
   result['results'].append({'id':ident,'repeat':repeat,'status':trace['final_verdict']['status'],'trace_file':'traces/'+name,'turns':len(trace['turns'])});save()
 result['summary']={'total':len(result['results']),'passed':sum(r['status']=='PASS' for r in result['results'])}
 result['pass_k']=[engine.pass_k([{**r,'core':True} for r in result['results']],k) for k in (1,3,8)]
 result['status']='COMPLETED';save();return result
