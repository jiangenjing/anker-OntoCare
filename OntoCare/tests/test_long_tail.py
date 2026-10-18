import unittest,json
from unittest.mock import patch
import app as m
import long_tail_knowledge as lt

class LongTailTests(unittest.TestCase):
 def setUp(self):m.SESSIONS.clear();self.c=m.app.test_client()
 def ask(self,text):return self.c.post('/api/chat',json={'message':text,'session_id':'longtail-test'}).json
 def test_inventory_and_clickable_sources(self):
  self.assertEqual(len(lt.ENTRIES),232)
  self.assertIn("long-tail-eval-007",lt.ENTRIES)
  self.assertEqual(len({i['category'] for i in lt.ENTRIES.values()}),19)
  for ident,item in lt.ENTRIES.items():
   self.assertTrue(item['strategy']);self.assertEqual(self.c.get('/api/sources/'+ident).status_code,200)
 def test_targeted_retrieval_and_unknown(self):
  self.assertEqual(lt.retrieve('退货标签打印不出来')[0]['id'],'long-tail-019')
  self.assertEqual(lt.retrieve('为什么在海关卡住')[0]['id'],'long-tail-008')
  self.assertEqual(lt.retrieve('帮我写一首诗'),[])
 def test_safe_fallback_no_false_facts(self):
  d=self.ask('退款什么时候到账？')
  self.assertEqual(d['trace']['long_tail']['classification'],'long_tail_candidate')
  self.assertIn('long-tail-015',[c['id'] for c in d['citations']])
  self.assertNotIn('3-5',d['reply']);self.assertNotIn('已退款',d['reply'])
 def test_real_model_path_receives_only_curated_strategy(self):
  def fake(system,user,timeout=45):
   payload=json.loads(user);strategies=[e for e in payload['evidence'] if e['id'].startswith('long-tail-')]
   self.assertEqual(len(strategies),1)
   self.assertEqual(strategies[0]['id'],'long-tail-035')
   self.assertEqual(strategies[0]['content']['evidence_level'],'SUPPLEMENTARY_REVIEW_STRATEGY_NOT_POLICY')
   self.assertNotIn('eufy 官网 > 订单详情',user)
   m.g.model_status='OK';m.g.model_calls+=1
   return json.dumps({'reply':'了解，您需要发票报销。\n\n目前只有发票核查策略，没有您购买渠道的开票入口资料。\n\n请先确认购买平台。','source_ids':['long-tail-035']})
  with patch.object(m,'LLM_KEY','test'),patch.object(m,'LLM_MODEL','test'),patch.object(m,'call_llm',side_effect=fake):
   d=self.ask('T2080 我要开具发票报销')
   self.assertEqual(d['trace']['model_calls'],1);self.assertEqual(d['trace']['answer_route'],'GROUNDED_LLM')
   self.assertIn('[1]',d['reply'])
 def test_common_faq_and_safety_stay_primary(self):
  d=self.ask('T8D04吸力很弱');self.assertEqual(d['trace']['answer_route'],'FAQ_CACHE')
  d=self.ask('T8D04吸力很弱而且出血');self.assertEqual(d['trace']['answer_route'],'HUMAN_REVIEW')
  self.assertNotEqual(d['trace']['long_tail']['classification'],'long_tail_candidate')
 def test_new_topic_does_not_reuse_last_strategy(self):
  self.ask('我要开具发票');d=self.ask('T2080 EB1L错误码')
  self.assertFalse(any(c['id']=='long-tail-035' for c in d['citations']))
