import unittest,json
from unittest.mock import patch
import app as m

class GroundedReplyTests(unittest.TestCase):
 def setUp(self):m.SESSIONS.clear();self.client=m.app.test_client()
 def test_cache_direct_skips_model(self):
  with patch.object(m,'GROUNDED_MODE',True),patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'call_llm') as llm:
   d=self.client.post('/api/chat',json={'message':'T8D04吸力很弱'}).json
   self.assertEqual(d['trace']['answer_route'],'FAQ_CACHE');self.assertEqual(d['trace']['model_calls'],0)
   self.assertTrue(d['citations']);llm.assert_not_called()
 def test_invalid_citations_fall_back(self):
  with patch.object(m,'GROUNDED_MODE',True),patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'call_llm',return_value='{"reply":"invented","source_ids":["not-a-source"]}'):
   d=self.client.post('/api/chat',json={'message':'T8D04自定义吸乳节奏如何设置'}).json
   self.assertNotIn('invented',d['reply']);self.assertEqual(d['trace']['model_status'],'INVALID_RESPONSE')

 def test_non_three_paragraph_response_falls_back(self):
  def fake(system,user,timeout=45):
   payload=json.loads(user)
   return json.dumps({'reply':'只有一段。','source_ids':[payload['evidence'][0]['id']]})
  with patch.object(m,'GROUNDED_MODE',True),patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'call_llm',side_effect=fake):
   d=self.client.post('/api/chat',json={'message':'T8D04自定义吸乳节奏如何设置'}).json
   self.assertEqual(d['trace']['model_status'],'INVALID_RESPONSE')
   self.assertNotEqual(d['reply'],'只有一段。')
 def test_emotion_and_no_fake_sla(self):
  def fake(system,user,timeout=45):
   payload=json.loads(user)
   self.assertEqual(payload['emotion_level'],'ANGRY')
   self.assertIsNone(payload['sla']);self.assertEqual(payload['executed_actions'],[])
   return json.dumps({'reply':'我理解您的困扰。\n\n需要人工核查。\n\n我已为您创建工单，24小时内专员跟进。','source_ids':[payload['evidence'][0]['id']]})
  with patch.object(m,'GROUNDED_MODE',True),patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'call_llm',side_effect=fake):
   d=self.client.post('/api/chat',json={'message':'T8D04自定义吸乳节奏如何设置，气死了'}).json
   self.assertEqual(d['trace']['model_status'],'INVALID_RESPONSE')
   self.assertNotIn('24小时',d['reply'])
