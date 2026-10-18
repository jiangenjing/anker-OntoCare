import unittest
from unittest.mock import patch
from pathlib import Path
import app as m
import user_experience as ux
class ExperienceTests(unittest.TestCase):
 def setUp(self):m.SESSIONS.clear();self.c=m.app.test_client()
 def ask(self,text):
  with patch.object(m,'LLM_KEY',''):
   return self.c.post('/api/chat',json={'session_id':'ux','message':text}).json
 def test_recent_order_choices_are_exact(self):
  items=ux.choices({'service_intent':'shipping'},m.ORDERS,m.PRODUCTS)
  self.assertEqual(len(items),3)
  self.assertEqual([i['date'] for i in items],sorted([i['date'] for i in items],reverse=True))
  for i in items:self.assertTrue(any(r.get('SKU')==i['sku'] and r.get('购买日期')==i['date'] for r in m.ORDERS[i['order_id'].upper()]['items']))
 def test_known_order_does_not_offer_unrelated_products(self):
  self.assertEqual(ux.choices({'order_id':'ANKER002'},m.ORDERS,m.PRODUCTS),[])
 def test_same_name_disambiguation(self):
  choices=ux.choices({'product_state':'CONFLICTED'},m.ORDERS,m.PRODUCTS)
  self.assertEqual({i['pn'] for i in choices},{'T2080','T8D04'})
  self.assertNotEqual(choices[0]['image']['image'],choices[1]['image']['image'])
 def test_dates_missing_last(self):
  orders={'X':{'order_id':'X','items':[{'SKU':'A','购买日期':None},{'SKU':'B','购买日期':'2026-09-01'}]}}
  self.assertEqual(ux.recent_items(orders)[0]['row']['SKU'],'B')
 def test_choice_continues_shipping(self):
  self.ask('物流怎么查');r=self.ask('我要查询订单 Anker002 中的商品 SKU T29C2001')
  self.assertEqual(r['trace']['order'],'ANKER002');self.assertEqual(m.SESSIONS['ux']['selected_sku'],'T29C2001')
  self.assertEqual(len(r['followups']['questions']),6)
 def test_diagrams_only_from_cited_sources(self):
  self.assertEqual(ux.diagrams([],m.qa.SOURCES),[])
  sid=next(k for k,v in m.qa.SOURCES.items() if 'install-the-filter.png' in v['Content'])
  result=ux.diagrams([m.qa.citation(sid)],m.qa.SOURCES)
  self.assertTrue(result);self.assertTrue(all(d['source_url']==m.qa.citation(sid)['url'] for d in result))
 def test_feedback_validation_and_storage(self):
  self.assertEqual(self.c.post('/api/feedback',json={}).status_code,400)
  self.ask('Anker002');self.assertEqual(self.c.post('/api/feedback',json={'session_id':'ux','turn':1,'rating':'unresolved','detail':'wrong item'}).status_code,200)
  self.assertEqual(m.SESSIONS['ux']['feedback']['1']['detail'],'wrong item')
 def test_official_images_local(self):
  for image in ux.IMAGES.values():
   self.assertTrue((Path(m.__file__).parent/'static'/image['image'].lstrip('/')).is_file())
   self.assertIn('eufy.com',image['source']) if 'ankerjapan' not in image['source'] else None
 def test_initial_six_questions(self):
  d=self.c.get('/api/user-options').json;self.assertEqual(len(d['followups']['questions']),6)
  self.assertTrue(d['choices'])
  self.assertTrue(all(c['kind']=='order' and c['order_id'] and c['image'] for c in d['choices']))
  self.assertEqual([c['date'] for c in d['choices']], sorted([c['date'] for c in d['choices']],reverse=True))
