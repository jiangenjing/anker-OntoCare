import unittest
from unittest.mock import patch
import app as m

class FollowupTests(unittest.TestCase):
 def setUp(self):m.SESSIONS.clear();self.client=m.app.test_client()
 def ask(self,text):return self.client.post('/api/chat',json={'message':text,'session_id':'followup'}).json
 def test_each_turn_retrieves_and_updates(self):
  with patch.object(m.qa,'retrieve',wraps=m.qa.retrieve) as retrieve:
   first=self.ask('T8D04吸力很弱')['followups'];count=retrieve.call_count
   q=first['questions'][0]['text'];second=self.ask(q)['followups']
   self.assertGreater(retrieve.call_count,count);self.assertEqual(second['ontology']['revision'],2)
   self.assertNotIn(q,[x['text'] for x in second['questions']])
   for item in second['questions']:
    for sid in item['source_ids']:self.assertEqual(self.client.get('/api/sources/'+sid).status_code,200)
 def test_shipping_switch_replaces_product_questions(self):
  self.ask('T8D04吸力很弱');d=self.ask('订单 Anker002 只收到配件，扫地机还没到')['followups']
  self.assertEqual(d['ontology']['intent'],'shipping')
  self.assertTrue(all('ANKER002' in q['text'] for q in d['questions']))
  self.assertFalse(any(n['type']=='KnowledgeItem' for n in d['ontology']['nodes']))
 def test_product_switch_does_not_leak_pump_sources(self):
  self.ask('T8D04吸力很弱');d=self.ask('T2080 EB1L加水异常')['followups']
  self.assertEqual(d['ontology']['product'],'T2080')
  self.assertFalse(any(s.startswith('b-') for q in d['questions'] for s in q['source_ids']))
 def test_snapshot_restores_recommendations(self):
  d=self.ask('T8D04吸力很弱');snapshot=self.client.get('/api/session/followup').json
  self.assertEqual(d['followups'],snapshot['followups'])
