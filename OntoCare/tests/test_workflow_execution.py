import unittest
from unittest.mock import patch
import app as m

class WorkflowExecution(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear();self.client=m.app.test_client()
 def ask(self,text,sid='case'):
  r=self.client.post('/api/chat',json={'message':text,'session_id':sid});self.assertEqual(r.status_code,200)
  d=r.json;self.assertTrue(d['citations'])
  for c in d['citations']:self.assertEqual(self.client.get(c['url']).status_code,200)
  return d
 def test_steps_failure_escalation_and_resolution(self):
  with patch.object(m,'call_llm') as llm:
   self.ask('T8D04吸力很弱')
   d=self.ask('第二步没看懂');self.assertIn('装好',d['reply']);self.assertEqual(d['trace']['workflow_history'],[])
   d=self.ask('试过了，还是不行');self.assertIn('第 2 步',d['reply'])
   d=self.ask('下一步');self.assertIn('第 3 步',d['reply'])
   d=self.ask('全部都试过了还是不行');self.assertEqual(d['trace']['workflow_status'],'NEEDS_HUMAN_REVIEW')
   d=self.ask('下一步');self.assertEqual(d['trace']['workflow_status'],'NEEDS_HUMAN_REVIEW')
   self.assertNotIn('第 2 步',d['reply'])
   llm.assert_not_called()
 def test_resolution_is_user_reported(self):
  self.ask('T8D04吸力很弱');d=self.ask('好了');self.assertEqual(d['trace']['workflow_status'],'RESOLVED');self.assertIn('你反馈',d['reply'])
 def test_topic_switch_drops_old_steps(self):
  self.ask('T8D04吸力很弱');self.ask('Anker002发货了吗');d=self.ask('下一步')
  self.assertNotEqual(d['trace']['answer_route'],'WORKFLOW_FOLLOWUP')
 def test_sessions_do_not_share_progress(self):
  self.ask('T8D04吸力很弱','one');self.ask('下一步','one');d=self.ask('下一步','two')
  self.assertNotEqual(d['trace']['answer_route'],'WORKFLOW_FOLLOWUP')
 def test_risk_overrides_step_continuation(self):
  self.ask('T8D04吸力很弱');d=self.ask('试过了但是出血了')
  self.assertEqual(d['trace']['answer_route'],'HUMAN_REVIEW');self.assertIsNone(d['trace']['workflow_status'])
 def test_product_change_resets_workflow(self):
  self.ask('T8D04吸力很弱');self.ask('T2353充不上电');d=self.ask('下一步')
  self.assertNotIn('鸭嘴阀',d['reply']);self.assertIn('充电触点',d['reply'])

 def test_error_code_continues_with_source(self):
  self.ask('T2080 EB1L加水异常');d=self.ask('下一步')
  self.assertIn('第 2 步',d['reply']);self.assertIn('进水口',d['reply'])
  self.assertEqual(d['trace']['answer_route'],'WORKFLOW_FOLLOWUP')
  self.ask('下一步');d=self.ask('下一步')
  self.assertIn('最后一步',d['reply']);self.assertEqual(d['trace']['workflow_status'],'ACTIVE')
