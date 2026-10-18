import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app as m
from benchmark import api
from benchmark.agents.red_team import RedTeam
from benchmark.agents import judge,blue_team
from benchmark.orchestrator import runner
from benchmark.orchestrator.chaos import inject

class RedBlueTests(unittest.TestCase):
 def setUp(self):
  self.c=m.app.test_client();self.cases,self.personas=runner.load_data();self.persona=copy.deepcopy(self.personas[0]);self.case=next(c for c in self.cases if c['id']=='U093')
 def test_first_message_verbatim_and_patience_budget(self):
  red=RedTeam(self.persona,8);self.assertEqual(red.first()['input'],self.persona['first_message']);self.assertEqual(red.budget,2)
 def test_escalation_is_code_controlled_and_clamped(self):
  red=RedTeam(self.persona);red.state['frustration']=9
  result=red.next([{'input':'x','response':{'reply':'Please provide more details.'}}])
  self.assertEqual(result['state']['frustration'],10);self.assertEqual(result['state_change']['frustration'],{'from':9,'to':10})
 def test_red_rejects_invented_identifiers(self):
  with patch('benchmark.agents.red_team.complete',return_value=({'input':'My Anker999 order costs $999.','language':'en'},{'status':'OK','calls':1})):
   result=RedTeam(self.persona,mode='llm').next([{'input':'x','response':{'reply':'Please provide details'}}])
  self.assertEqual(result['generation']['status'],'REJECTED');self.assertNotIn('Anker999',result['input'])
 def test_red_can_question_verified_tracking_but_not_invent_it(self):
  history=[{'input':'x','response':{'reply':'Please check tracking.'}}]
  with patch('benchmark.agents.red_team.complete',return_value=({'input':'Could you check Anker1234567?','language':'en'},{'status':'OK','calls':1})):
   result=RedTeam(self.persona,mode='llm').next(history,[{'id':'order-2','content':'Tracking Anker1234567'}])
  self.assertEqual(result['generation']['status'],'OK');self.assertIn('Anker1234567',result['input'])
 def test_judge_receives_previous_customer_statement_as_unverified_context(self):
  def complete(system,payload):
   statement=next(s for s in payload['sources'] if s['id']=='customer-statement-1')
   self.assertEqual(statement['content']['customer_statement'],'Only the parts arrived.')
   self.assertEqual(statement['content']['evidence_level'],'UNVERIFIED_CUSTOMER_REPORT_NOT_ORDER_FACT')
   return {'claims':[{'claim':'Customer reports only parts arrived','supported':True,'source_ids':['customer-statement-1']}],'tone':4,'action_legality':'PASS','goal_achieved':False},{'status':'OK','calls':1}
  turn={'input':'Next step?','status':200,'response':{'reply':'You said only the parts arrived.','citations':[{'id':'rule'}],'trace':{}}}
  with patch('benchmark.agents.judge.complete',side_effect=complete):
   result=judge.evaluate(turn,self.case,[{'id':'rule'}],set(),True,conversation=[{'input':'Only the parts arrived.'},turn])
  self.assertEqual(result['faithfulness'],1);self.assertEqual(result['semantic_status'],'ESTIMATE')
 def test_red_model_error_has_language_preserving_fallback(self):
  for lang in ('nl','fr','de'):
   p=copy.deepcopy(self.persona);p['tier1_demographics']['language']=lang
   with patch('benchmark.agents.red_team.complete',return_value=(None,{'status':'ERROR','calls':1})):
    result=RedTeam(p,mode='llm').next([{'input':'x','response':{'reply':'x'}}])
   self.assertEqual(result['language'],lang);self.assertEqual(result['generation']['status'],'ERROR');self.assertTrue(result['input'])
 def test_judge_unknown_order_clarification_not_hallucination(self):
  turn={'input':'Anker999','status':200,'response':{'reply':'Order Anker999 not found.','citations':[{'id':'rule'}],'trace':{'allowed':[]}}}
  result=judge.evaluate(turn,self.case,[{'id':'rule','content':'lookup unknown'}],{'ANKER001'})
  self.assertTrue(next(c['passed'] for c in result['checks'] if c['name']=='no_invented_order'))
  turn['response']['reply']='Anker999 was shipped.'
  self.assertFalse(next(c['passed'] for c in judge.evaluate(turn,self.case,[{'id':'rule'}],{'ANKER001'})['checks'] if c['name']=='no_invented_order'))
 def test_judge_never_invents_unmeasured_scores(self):
  turn={'input':'hi','status':200,'response':{'reply':'Hello','citations':[{'id':'rule'}],'trace':{}}}
  result=judge.evaluate(turn,self.case,[{'id':'rule'}],set());self.assertIsNone(result['faithfulness']);self.assertIsNone(result['tone']);self.assertIsNone(result['final_state_match'])
 def test_judge_rejects_invalid_schema(self):
  with patch('benchmark.agents.judge.complete',return_value=({'tone':100},{'status':'OK','calls':1})):
   d=judge.evaluate({'input':'hi','status':200,'response':{'reply':'hi','trace':{}}},self.case,[],set(),True)
  self.assertEqual(d['semantic_status'],'INVALID_RESPONSE')
 def test_historical_trace_not_misrepresented_as_turn_scores(self):
  row={'trajectory':[{'input':'x','response':{'reply':'y'}}],'status':'PASS','checks':[],'judge':{'tone':4},'mode':'offline','repeat':1}
  d=runner.historical_trace(self.case,row);self.assertIsNone(d['turns'][0]['judge']['tone']);self.assertEqual(d['trajectory_judge']['tone'],4)
 def test_api_validates_ids_limits_and_offline(self):
  for body in ({'case_ids':['../../secret']},{'max_turns':9},{'max_turns':True},{'mode':'offline','judge':True},{'repeats':2},{'fault':'bad'}):
   self.assertEqual(self.c.post('/api/benchmark/run',json=body).status_code,400)
 def test_api_rejects_cross_origin_and_remote_access(self):
  self.assertEqual(self.c.post('/api/benchmark/run',json={},headers={'Origin':'https://evil.invalid'}).status_code,403)
  self.assertEqual(self.c.get('/api/benchmark/trace/A003',environ_base={'REMOTE_ADDR':'10.1.2.3'}).status_code,403)
 def test_history_endpoint_and_missing_trace(self):
  d=self.c.get('/api/benchmark/trace/A003').json;self.assertEqual(d['case_id'],'A003');self.assertTrue(d['turns'])
  self.assertEqual(self.c.get('/api/benchmark/trace/NOPE').status_code,404)
  self.assertEqual(self.c.get('/api/benchmark/trace/U093?run_id=bad').status_code,404)
 def test_new_api_launches_subprocess_without_clearing_sessions(self):
  with tempfile.TemporaryDirectory() as td,patch.object(api,'OUTPUT',Path(td)),patch.dict(api._jobs,{},clear=True),patch.object(api.subprocess,'Popen') as proc:
   proc.return_value.poll.return_value=None;m.SESSIONS['active-demo']={'kept':True}
   response=self.c.post('/api/benchmark/run',json={'case_ids':['U093'],'mode':'offline'})
   self.assertEqual(response.status_code,202);self.assertTrue(m.SESSIONS['active-demo']['kept']);self.assertTrue(proc.called)
   self.assertEqual(self.c.post('/api/benchmark/run',json={}).status_code,409)
 def test_chaos_hits_and_restores_transport(self):
  import urllib.request
  original=urllib.request.urlopen;counter={'fault_hits':0}
  with inject(m,'rate_limit',counter):
   with self.assertRaises(Exception):urllib.request.urlopen('https://not-called.invalid')
  self.assertEqual(counter['fault_hits'],1);self.assertIs(urllib.request.urlopen,original)
 def test_dynamic_runner_keeps_real_first_message_and_no_semantic_score_offline(self):
  config={'case_ids':['U093'],'mode':'offline','red_mode':'scripted','max_turns':2,'repeats':1,'judge':False,'fault':None}
  with tempfile.TemporaryDirectory() as td:
   result=runner.run(config,td);trace=json.loads((Path(td)/'traces/U093-1.json').read_text())
  self.assertEqual(result['status'],'COMPLETED');self.assertEqual(trace['turns'][0]['red_team']['input'],self.persona['first_message']);self.assertEqual(len(trace['turns']),2)
  self.assertTrue(all(t['judge']['tone'] is None for t in trace['turns']))
  blue=trace['turns'][0]['blue_team']
  self.assertTrue(blue['ontology']['nodes'])
  self.assertTrue(any(e.get('citations') for e in blue['events']))
  self.assertTrue(all(e['type']=='progress' for e in blue['events']))
  self.assertIsNone(result['pass_k'][1]['rate'])

if __name__=='__main__':unittest.main()
