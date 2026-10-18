import json
import unittest
from unittest.mock import patch
import app as m

class MailWorkflowTests(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear();self.client=m.app.test_client()
 def draft(self,row=None,text=None,language='en'):
  r=next((x for x in m.mail.MAILS['rows'] if x['source_row']==row),None)
  response=self.client.post('/api/mail/stream',json={'ticket_row':row,'message':text if text is not None else r['客户首封邮件内容'],'language':language})
  self.assertEqual(response.status_code,200)
  events=[json.loads(line) for line in response.data.splitlines()]
  self.assertEqual(events[-1]['type'],'result',events)
  self.assertTrue(any(e['type']=='progress' for e in events))
  d=events[-1]['data'];self.assertTrue(d['draft']);self.assertEqual(d['status'],'DRAFT_ONLY')
  for c in d['citations']:self.assertEqual(self.client.get(c['url']).status_code,200)
  self.assertFalse(any(k.startswith('mail-') for k in m.SESSIONS))
  return d
 def test_all_excel_emails_generate_cited_drafts(self):
  with patch.object(m,'LLM_KEY',''):
   for r in m.mail.MAILS['rows']:
    with self.subTest(row=r['source_row']):self.draft(r['source_row'])
 def test_shipping_includes_all_parcels(self):
  d=self.draft(3);self.assertIn('Anker1234567-2',d['draft']);self.assertIn('Anker1234567-3',d['draft'])
 def test_safety_precedes_charge_cache(self):
  with patch.object(m,'call_llm') as llm:
   d=self.draft(46);self.assertEqual(d['route'],'SAFETY_REVIEW');self.assertIn('stop using',d['draft']);llm.assert_not_called()
 def test_attempted_steps_are_not_repeated(self):
  d=self.draft(32);self.assertEqual(d['route'],'ATTEMPTED_STEPS_REVIEW');self.assertIn('already attempted',d['draft'])
 def test_edited_email_drops_original_order(self):
  d=self.draft(3,'My T8D04 breast pump has no suction.');self.assertNotIn('ANKER002',d['draft'].upper());self.assertFalse(any(c['kind']=='email' for c in d['citations']))
 def test_mail_isolated_from_chat(self):
  self.client.post('/api/chat',json={'session_id':'customer','message':'Anker002发货了吗'})
  d=self.draft(text='My T8D04 breast pump has no suction.');self.assertNotIn('ANKER002',d['draft'].upper());self.assertIn('customer',m.SESSIONS)
 def test_english_and_chinese(self):
  d=self.draft(12,language='zh');self.assertIn('EB1L',d['draft']);self.assertIn('你好',d['draft']);self.assertTrue(any(c['id']=='r-482' for c in d['citations']))
 def test_empty_and_oversize_rejected(self):
  for text in ['', 'x'*20001]:self.assertEqual(self.client.post('/api/mail/stream',json={'message':text}).status_code,400)
 def test_source_html_is_escaped(self):
  row=m.mail.MAILS['rows'][0]
  with patch.dict(row,{'客户首封邮件内容':'<script>alert(1)</script>'}):
   d=self.client.get('/api/sources/mail-2').data.decode();self.assertIn('&lt;script&gt;',d);self.assertNotIn('<script>',d)

 def test_attempted_chat_suggestion(self):
  d=self.client.post('/api/chat',json={'message':'T2080 清洁充电触点后仍充不上电'}).json
  self.assertEqual(d['trace']['answer_route'],'ATTEMPTED_STEPS_REVIEW');self.assertIn('r-474',[c['id'] for c in d['citations']])

 def test_real_suction_mail_uses_cache(self):
  with patch.object(m,'call_llm') as llm:
   d=self.draft(55);self.assertEqual(d['route'],'FAQ_CACHE');llm.assert_not_called()

 def test_melting_does_not_invent_injury(self):
  d=self.draft(text='T8D04 charging case is melting.')
  self.assertEqual(d['route'],'SAFETY_REVIEW')
  self.assertNotIn('you were hurt',d['draft'])
  self.assertIn('stop using',d['draft'])
