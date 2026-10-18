import json
import unittest
from unittest.mock import patch
import analytics_assistant as a
import app

class AnalyticsAssistantTests(unittest.TestCase):
 def ask(self,q,context=None,model=None):
  return a.answer(q,context or {},model or (lambda *args:None))
 def test_x10_is_not_rc3(self):
  r=self.ask('X10 Pro 最近工单为什么多？')
  self.assertIn('14 条',r['reply']);self.assertIn('22.2%',r['reply'])
  self.assertIn('无法判断',r['reply'])
  self.assertEqual(r['context']['rule_id'],'DO-OPS-FOCUS')
  self.assertEqual(len(r['evidence']),14)
  self.assertEqual([x['name'] for x in r['tool_calls']],['ReadOntology','ReadTrace'])
  self.assertEqual(r['tool_calls'][1]['result']['audit_ids'],[])
 def test_rc3_uses_actual_rows_and_limits(self):
  r=self.ask('RC3 候选有哪些问题特征？')
  self.assertEqual(set(r['evidence']),{'19','28'})
  self.assertIn('不能',r['trace_chain'][2]['definition'])
  self.assertIn('3212',r['reply'])
 def test_no_warranty_cases_is_not_invented(self):
  r=self.ask('过保临界点工单有什么共同点？')
  self.assertEqual(r['evidence'],{})
  self.assertIn('4 条可核算',r['reply']);self.assertIn('59 条',r['reply'])
 def test_followup_keeps_selection_but_new_topic_resets(self):
  r=self.ask('X10 Pro 为什么多？')
  follow=self.ask('这些应该怎么改善？',r['context'])
  self.assertEqual(follow['context']['product'],'X10 Pro')
  next_topic=self.ask('RC3 怎么改？',follow['context'])
  self.assertIsNone(next_topic['context']['product'])
 def test_llm_gets_evidence_and_valid_reply_used(self):
  def model(system,payload):
   data=json.loads(payload);self.assertIn('source_rows',data)
   self.assertNotIn('order_snapshot',data)
   return json.dumps({'advice':'建议先抽查原文与复现条件。','source_rows':data['source_rows'][:1]})
  r=self.ask('X10 Pro 为什么多？',model=model)
  self.assertIn('LLM',r['mode']);self.assertIn('建议先抽查',r['reply'])
 def test_bad_citations_or_invented_counts_fall_back(self):
  for output in [{'advice':'建议核查','source_rows':[999]}, {'advice':'有 888 件电池故障','source_rows':[4]}, {'advice':'分析','source_rows':[]}]:
   r=self.ask('X10 Pro 为什么多？',model=lambda *args:json.dumps(output))
   self.assertNotIn('LLM',r['mode']);self.assertNotIn('888',r['reply'])
 def test_evidence_is_original(self):
  report=json.loads((a.ROOT/'reports/attribution_report.json').read_text())
  r=self.ask('RC3 的问题')
  for key,row in r['evidence'].items():
   source=next(t for t in report['tickets'] if str(t['row'])==key)
   self.assertEqual(row['email'],source['email'])
 def test_api_validation_and_unavailable_model(self):
  client=app.app.test_client()
  self.assertEqual(client.post('/api/analytics/chat',json={'message':''}).status_code,400)
  with patch.object(app,'call_llm',return_value=None):
   result=client.post('/api/analytics/chat',json={'message':'RC3 怎么改？'})
  self.assertEqual(result.status_code,200)
  self.assertIn('规则摘要',result.json['mode'])
