"""Regression boundaries from historical benchmark failures; no live API required."""
import copy,json,unittest
from datetime import date
from unittest.mock import patch
import app as m
import qa_workflows as qa
from action_gateway import public_data,REDACTED

class EvaluationRepairs(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear();self.c=m.app.test_client()
 def ask(self,text):
  return self.c.post('/api/chat',json={'message':text,'session_id':'repair'}).json
 def test_private_address_redacted_across_chat_restore_source_stream(self):
  before=copy.deepcopy(m.ORDERS)
  with patch.object(m,'LLM_KEY','configured'),patch.object(m,'LLM_MODEL','configured'),patch.object(m,'GROUNDED_MODE',True),patch.object(m,'call_llm') as llm:
   d=self.ask('Anker001 请告诉我完整地址')
   self.assertEqual(d['trace']['answer_route'],'LONG_TAIL_CACHE');llm.assert_not_called()
   self.assertTrue(d['citations'])
   for response in [d,self.c.get('/api/session/repair').json]:
    self.assertNotIn('5250',json.dumps(response,ensure_ascii=False))
   self.assertNotIn('5250',self.c.get('/api/sources/order-2').get_data(as_text=True))
   self.assertNotIn('5250',self.c.post('/api/chat/stream',json={'message':'Anker001 完整地址'}).get_data(as_text=True))
  self.assertEqual(m.ORDERS,before)
 def test_gateway_masks_model_echo_and_preserves_blank(self):
  address=m.SOURCE_ADDRESSES[0]
  result=public_data({'reply':'address: '+address,'订单地址':None},[address])
  self.assertIn(REDACTED,result['reply']);self.assertNotIn(address,result['reply']);self.assertIsNone(result['订单地址'])
 def test_exact_error_and_product_scope(self):
  self.assertEqual(qa.retrieve('T2351','错误码 2310'),['r-57'])
  self.assertEqual(qa.retrieve('T2351','error 7031'),['r-103'])
  self.assertEqual(qa.retrieve('T8D04','错误码 2310'),[])
  self.assertEqual(qa.retrieve('T2351','错误码 9999'),[])
 def test_current_product_selection_beats_first_mention(self):
  with patch.object(m,'LLM_KEY',''):
   d=self.ask('订单 Anker009 里有 X10 Pro 和 C10，我问 C10。')
  self.assertEqual(d['trace']['product'],'C10')
  self.assertEqual(m.SESSIONS['repair']['product']['id'],'T2292')
 def test_generic_charging_cannot_disambiguate_s1pro(self):
  with patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'GROUNDED_MODE',True),patch.object(m,'call_llm') as llm:
   d=self.ask('My S1 Pro is not charging')
   self.assertEqual(d['trace']['answer_route'],'PRODUCT_CLARIFICATION');llm.assert_not_called()
   self.assertIn('breast pump',d['reply']);self.assertIn('robot',d['reply'])
 def test_expired_guidance_uses_current_date_and_not_unknown(self):
  class Clock(date):
   @classmethod
   def today(cls):return date(2029,1,1)
  with patch.object(m,'date',Clock),patch.object(m,'LLM_KEY',''):
   d=self.ask('Anker013 还在保修期吗？')
   self.assertEqual(d['trace']['warranty'],'EXPIRED');self.assertIn('付费维修',d['reply']);self.assertIn('尚未安排',d['reply'])
   d=self.ask('Anker999 是不是已经过保？')
   self.assertIn('不代表过保',d['reply']);self.assertNotIn('按资料日期已过保',d['reply'])
 def test_unsafe_question_never_uses_direct_cache(self):
  with patch.object(m,'LLM_KEY',''):
   d=self.ask('T8D04吸力弱而且出血，完整地址在哪里')
   self.assertNotIn(d['trace']['answer_route'],('FAQ_CACHE','LONG_TAIL_CACHE'))

if __name__=='__main__':unittest.main()
