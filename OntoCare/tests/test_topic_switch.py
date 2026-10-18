import unittest
from unittest.mock import patch
import app as m
ERROR = 'Product Name: S1 Pro Product PN: T2080A Product SN: 12345678A Problem Type: ERROR Problem Code: 2107332– Problem Push: EB1L: The robot encountered an error while adding clean water. Task ended. Click to contact customer service for assistance. Problem Description: EB1L: The robot encountered an error while adding clean water. Task ended. Problem Upload Images: []'
TRACKING = 'I’ve tried to put my tracking number in to look for my order and it is not working. Do you know when I will be getting my order?'
class TopicSwitch(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear(); self.client=m.app.test_client()
 def ask(self,text):
  r=self.client.post('/api/chat',json={'message':text,'session_id':'switch'});self.assertEqual(r.status_code,200);return r.json
 def test_structured_fault_overrides_shipping(self):
  self.ask('Anker002 T2080GA1发货了吗')
  with patch.object(m,'call_llm') as llm:
   d=self.ask(ERROR)
   self.assertNotIn('物流记录',d['reply']);self.assertIn('EB1L',d['reply']);self.assertIn('water inlet',d['reply']);self.assertEqual(d['trace']['response_language'],'en')
   self.assertEqual(d['citations'][0]['id'],'r-482');llm.assert_not_called()
 def test_tracking_failure_answers_eta_and_checks_context(self):
  self.ask('Anker002 T2080GA1发货了吗')
  d=self.ask(TRACKING)
  self.assertIn('cannot confirm an ETA',d['reply']);self.assertIn('different one',d['reply']);self.assertEqual(d['trace']['response_language'],'en')
 def test_unknown_code_not_replaced_with_similar_code(self):
  self.ask('Anker002发货了吗')
  d=self.ask('T2080 错误码 EB1Z 加水异常')
  self.assertNotIn('物流记录',d['reply']);self.assertNotIn('EB1L',d['reply']);self.assertIn('完整',d['reply'])
