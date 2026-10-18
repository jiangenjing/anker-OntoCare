import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app as m

class HandoffTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=patch.object(m.handoffs,'ROOT',Path(self.tmp.name));self.root.start();m.SESSIONS.clear();self.client=m.app.test_client()
 def tearDown(self):self.root.stop();self.tmp.cleanup()
 def ask(self):return self.client.post('/api/chat',json={'session_id':'customer','message':'T8D04没有吸力'}).json
 def test_ninth_turn_and_duplicate_submission(self):
  for n in range(1,10):
   d=self.ask();self.assertEqual(d['turn_count'],n);self.assertEqual(d['handoff_available'],n>8)
   if n==8:self.assertEqual(self.client.post('/api/handoffs',json={'session_id':'customer','channel':'email'}).status_code,400)
  r=self.client.post('/api/handoffs',json={'session_id':'customer','channel':'email'}).json['record']
  again=self.client.post('/api/handoffs',json={'session_id':'customer','channel':'email'}).json['record']
  self.assertEqual(r['id'],again['id']);self.assertIsNone(r['customer_id']);self.assertEqual(len(self.client.get('/api/handoffs').json['records']),1)
  self.assertEqual(self.client.get('/api/sources/handoff-'+r['id']).status_code,200)
  response=self.client.post('/api/mail/stream',json={'handoff_id':r['id'],'message':r['message'],'language':'zh'})
  events=[json.loads(x) for x in response.data.splitlines()];d=events[-1]['data']
  self.assertIn('吸',d['draft']);self.assertTrue(any(c['id']=='handoff-'+r['id'] for c in d['citations']))
  self.assertEqual(d['status'],'DRAFT_ONLY')
 def test_missing_session_and_invalid_channel(self):
  self.assertEqual(self.client.post('/api/handoffs',json={'session_id':'missing','channel':'email'}).status_code,400)
  for _ in range(9):self.ask()
  self.assertEqual(self.client.post('/api/handoffs',json={'session_id':'customer','channel':'send'}).status_code,400)
 def test_human_request_is_recorded_not_connected(self):
  for _ in range(9):self.ask()
  d=self.client.post('/api/handoffs',json={'session_id':'customer','channel':'human'}).json
  self.assertEqual(d['record']['status'],'WAITING_REVIEW');self.assertIn('尚未接通',d['message'])
 def test_new_case_resets_counter(self):
  for _ in range(9):self.ask()
  d=self.client.post('/api/chat',json={'session_id':'customer','message':'T8D04没有吸力','new_case':True}).json
  self.assertEqual(d['turn_count'],1);self.assertFalse(d['handoff_available'])

 def test_shared_stylesheet_is_served(self):
  r=self.client.get('/anker.css');self.assertEqual(r.status_code,200)
  self.assertIn(b'.view-tabs',r.data);r.close()

 def test_shipping_suggestion_after_troubleshooting(self):
  self.ask()
  d=self.client.post('/api/chat',json={'session_id':'customer','message':'订单 Anker002 只收到配件，扫地机还没到'}).json
  self.assertIn('Anker1234567-2',d['reply']);self.assertIn('Anker1234567-3',d['reply'])
  self.assertNotIn('请描述具体症状',d['reply'])
