import json,unittest
from pathlib import Path
from unittest.mock import patch
import app as m
import long_tail_knowledge as lt

class JsonLongTailTests(unittest.TestCase):
 def test_complete_records_only(self):
  rows=[i for i in lt.ENTRIES.values() if i['id'].startswith('long-tail-json-')]
  self.assertEqual(len(rows),119)
  self.assertNotIn('long-tail-json-C015',lt.ENTRIES)
  audit=json.loads((lt.DATA_DIR/'导入审计.json').read_text())
  self.assertTrue(audit['truncated'])
 def test_pn_isolation_and_explicit_override(self):
  self.assertTrue(any(i['id']=='long-tail-json-C004' for i in lt.retrieve('T8170 夜视效果差')))
  self.assertFalse(any(i['id'].startswith('long-tail-json-C') for i in lt.retrieve('T2351 夜视效果差',pn='T8170')))
  self.assertFalse(any(i.get('pn') for i in lt.retrieve('夜视效果差')))
 def test_shared_error_code_is_scoped(self):
  a=lt.retrieve('T2351 6011');b=lt.retrieve('T2352 6011')
  self.assertIn('long-tail-json-R034',[i['id'] for i in a])
  self.assertNotIn('long-tail-json-R001',[i['id'] for i in a])
  self.assertIn('long-tail-json-R001',[i['id'] for i in b])
 def test_no_template_order_or_business_promise(self):
  for i in lt.ENTRIES.values():
   if i['id'].startswith('long-tail-json-L'):
    self.assertNotIn('Anker1234567',i['strategy']);self.assertNotIn('Anker001',i['strategy'])
  self.assertNotIn('贴一小块胶带',lt.ENTRIES['long-tail-json-R031']['strategy'])
 def test_model_receives_json_strategy_and_citation(self):
  seen=[]
  def fake(system,user,timeout=45):
   payload=json.loads(user);seen.extend(payload['evidence'])
   m.g.model_status='OK';m.g.model_calls+=1
   return json.dumps({'reply':'了解您希望指定承运商。\n\n需要核对购买渠道规则，目前没有已确认政策。\n\n请告诉我购买渠道。','source_ids':['long-tail-json-L009']})
  with patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'call_llm',side_effect=fake):
   with m.app.test_client() as c:
    d=c.post('/api/chat',json={'message':'客户要求指定承运商','session_id':'json-test'}).json
    self.assertIn('long-tail-json-L009',[x['id'] for x in d['citations']])
    self.assertIn('[1]',d['reply'])
  self.assertTrue(any(e['id']=='long-tail-json-L009' for e in seen))
 def test_continuous_topic_switch(self):
  with patch.object(m,'LLM_KEY',''):
   with m.app.test_client() as c:
    for q,expected,excluded in [('客户要求指定承运商','long-tail-json-L009','long-tail-json-L006'),('订单号查不到，但客户坚称已下单','long-tail-json-L006','long-tail-json-L009')]:
     d=c.post('/api/chat',json={'message':q,'session_id':'json-continuous'}).json
     ids=[x['id'] for x in d['citations']]
     self.assertIn(expected,ids);self.assertNotIn(excluded,ids)

 def test_melting_uses_safety_route_without_llm(self):
  with patch.object(m,'LLM_KEY',''):
   with m.app.test_client() as c:
    d=c.post('/api/chat',json={'message':'T8D04 充电盒或配件熔化','session_id':'json-safety'}).json
    self.assertEqual(d['trace']['answer_route'],'HUMAN_REVIEW')
    self.assertFalse(any(x['id']=='long-tail-json-B010' for x in d['citations']))
