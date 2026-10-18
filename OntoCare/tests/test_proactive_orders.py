import unittest
from unittest.mock import patch
import app as m
class ProactiveOrdersTests(unittest.TestCase):
 def setUp(self):m.SESSIONS.clear();self.client=m.app.test_client()
 def ask(self,text):
  with patch.object(m,'LLM_KEY',''):
   r=self.client.post('/api/chat',json={'session_id':'proactive','message':text});self.assertEqual(r.status_code,200);return r.json
 def test_product_alone_lists_exact_recent_candidates(self):
  d=self.ask('我的产品是吸奶器 T8D04')
  self.assertEqual(d['trace']['answer_route'],'ORDER_CANDIDATES');self.assertTrue(d['selection_cards'])
  dates=[]
  for c in d['selection_cards']:
   self.assertTrue(c['sku'].startswith('T8D04'));self.assertFalse(c['ownership_verified'])
   dates.append(c['date']);self.assertIn(c['source_id'],[s['id'] for s in d['citations']])
  self.assertEqual(dates,sorted(dates,reverse=True));self.assertFalse(m.SESSIONS['proactive'].get('order_id'))
 def test_conflict_keeps_product_and_clears_wrong_warranty(self):
  self.ask('我的产品是吸奶器 T8D04');d=self.ask('Anker002这个是订单号啊')
  self.assertEqual(m.SESSIONS['proactive']['product']['id'],'T8D04');self.assertEqual(d['trace']['warranty'],'UNKNOWN')
  self.assertTrue(d['selection_cards']);self.assertIsNone(d['order_snapshot']);self.assertIn('不匹配',d['reply'])
  chosen=d['selection_cards'][0];next_reply=self.ask(chosen['message'])
  self.assertEqual(next_reply['order_snapshot']['order_id'].upper(),chosen['order_id'].upper())
  self.assertEqual(next_reply['trace']['ownership_status'],'NOT_VERIFIED');self.assertFalse(next_reply['selection_cards'])
 def test_decline_does_not_loop(self):
  self.ask('T8D04 吸奶器');d=self.ask('这些都不是我的订单');self.assertFalse(d['selection_cards']);self.assertIn('不会使用',d['reply'])
 def test_english(self):
  d=self.ask('My breast pump model is T8D04.');self.assertIn('Select an item',d['reply']);self.assertTrue(d['selection_cards'])
 def test_unknown_order_not_silently_selected(self):
  self.ask('我的吸奶器 T8D04');d=self.ask('Anker999');self.assertEqual(d['trace']['answer_route'],'ORDER_NOT_FOUND')
