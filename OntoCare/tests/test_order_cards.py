import unittest
from unittest.mock import patch
import app as m
import order_cards
class OrderCardTests(unittest.TestCase):
 def setUp(self):m.SESSIONS.clear();self.c=m.app.test_client()
 def ask(self,text):
  with patch.object(m,'LLM_KEY',''):
   return self.c.post('/api/chat',json={'session_id':'cards','message':text}).json
 def test_all_fields_exact_source(self):
  for oid,order in m.ORDERS.items():
   card=order_cards.build(m.lookup_order(oid))
   self.assertEqual(len(card['items']),len(order['items']))
   for item,source in zip(card['items'],order['items']):
    for key in order_cards.FIELDS:self.assertEqual(item['fields'][key],'未核验，已隐藏' if key=='订单地址' and source.get(key) else source.get(key))
    self.assertIn('订单地址',item['redacted_fields'])
    self.assertEqual(self.c.get(item['source_url']).status_code,200)
 def test_multi_item_order(self):
  d=self.ask('Anker002');self.assertEqual(len(d['order_card']['items']),2)
  self.assertEqual([i['fields']['SKU'] for i in d['order_card']['items']],['T2080GA1','T29C2001'])
  self.assertFalse(d['order_card']['ownership_verified'])
 def test_confirm_no_repeat_or_authorization(self):
  self.ask('Anker006');d=self.ask('是这笔订单，我要查询 Anker006')
  self.assertIsNone(d['order_card']);self.assertEqual(d['trace']['ownership_status'],'NOT_VERIFIED')
  self.assertEqual(d['order_snapshot']['order_id'].upper(),'ANKER006')
 def test_switch_and_not_found(self):
  self.ask('Anker002');self.assertEqual(self.ask('Anker006')['order_card']['order_id'].upper(),'ANKER006')
  self.assertIsNone(self.ask('Anker999')['order_snapshot'])
 def test_restore(self):
  d=self.ask('Anker002');snap=self.c.get('/api/session/cards').json
  self.assertEqual(snap['transcript'][-1]['order_card'],d['order_card'])
  self.assertEqual(snap['order_snapshot'],d['order_snapshot'])
 def test_tracking_not_order(self):
  self.assertIsNone(self.ask('Anker1234567-2')['order_card'])
 def test_card_script(self):
  r=self.c.get('/order_cards.js');self.assertEqual(r.status_code,200);r.close()

 def test_order_only_does_not_request_unknown_model(self):
  with patch.object(m,'LLM_KEY','configured'),patch.object(m,'LLM_MODEL','configured'),patch.object(m,'GROUNDED_MODE',True),patch.object(m,'call_llm') as llm:
   d=self.c.post('/api/chat',json={'session_id':'select','message':'Anker006'}).json
   self.assertEqual(d['trace']['answer_route'],'ORDER_SELECTION');llm.assert_not_called()
   self.assertIn('查询这件商品',d['reply']);self.assertTrue(all(c['kind']=='order' for c in d['citations']))
