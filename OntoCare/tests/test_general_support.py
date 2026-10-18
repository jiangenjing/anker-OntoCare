import json
import unittest
from pathlib import Path
import app as m
import long_tail_knowledge as lt

class GeneralSupportTests(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear();self.client=m.app.test_client()
 def ask(self,text):return self.client.post('/api/chat',json={'message':text,'session_id':'general-test'}).json
 def test_715_without_order_and_without_model_call(self):
  d=self.ask('我的 715 充电器无法为我的手机充电')
  self.assertEqual(d['trace']['answer_route'],'GENERAL_SUPPORT_CACHE')
  self.assertEqual(d['trace']['model_calls'],0)
  self.assertEqual(d['selection_cards'],[])
  self.assertIn('5 分钟',d['reply']);self.assertIn('[1]',d['reply'])
  self.assertNotIn('18W',d['reply']);self.assertNotIn('请告诉我具体产品型号和问题',d['reply'])
  self.assertTrue(d['citations'][0]['url'].startswith('https://service.anker.com/'))
  self.assertFalse(any('订单' in x['text'] for x in d['followups']['quick_replies']))
 def test_english_and_followup(self):
  d=self.ask('My 715 charger cannot charge my phone')
  self.assertIn('5 minutes',d['reply'])
  d=self.ask('I tried these checks, but it still does not work.')
  self.assertIn('phone model',d['reply']);self.assertNotIn('Wait 5 minutes',d['reply'])
 def test_safety_overrides_general(self):
  d=self.ask('我的715充电器冒烟了无法充电')
  self.assertEqual(d['trace']['answer_route'],'HUMAN_REVIEW')
  self.assertNotIn('重新连接',d['reply'])
 def test_wireless_is_not_wired(self):
  d=self.ask('无线充电器充不上电')
  self.assertIn('手机壳',d['reply']);self.assertNotIn('18W',d['reply'])
 def test_product_switch_clears_previous_order(self):
  self.ask('Anker002');d=self.ask('我的715充电器无法为手机充电')
  self.assertIsNone(m.SESSIONS['general-test']['product'])
  self.assertNotIn('Anker002',d['reply'])
  d=self.ask('T8D04吸力很弱')
  self.assertEqual(d['trace']['answer_route'],'FAQ_CACHE')
  self.assertNotIn('general_support',m.SESSIONS['general-test'])
 def test_business_request_not_swallowed(self):
  self.ask('715充电器不能充电');d=self.ask('我想申请退款')
  self.assertNotEqual(d['trace']['answer_route'],'GENERAL_SUPPORT_CACHE')
 def test_import_count_and_source_ids(self):
  entries=[e for e in lt.ENTRIES.values() if e['id'].startswith('long-tail-bilingual-')]
  self.assertEqual(len(entries),14)
  for e in entries:self.assertEqual(self.client.get('/api/sources/'+e['id']).status_code,200)
  self.assertIn('long-tail-bilingual-QA001',[e['id'] for e in lt.retrieve('我刚买就降价了，能退差价吗？')])
  self.assertFalse(any(e['id']=='long-tail-bilingual-R078' for e in lt.retrieve('E41 error',pn='T8D04')))
 def test_curated_policy_has_no_automatic_compensation(self):
  e=lt.ENTRIES['long-tail-bilingual-QA001']
  self.assertIn('不能',e['strategy']);self.assertNotIn('Anker offers',e['content'])
