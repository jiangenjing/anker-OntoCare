"""Regression examples from the independent evaluation and nearby boundary cases."""
import json,unittest
from unittest.mock import patch
import app as m
import attribution, customer_signals, grounded_response, mail_editing

class EvaluationRegressions(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear();self.client=m.app.test_client();self.key=patch.object(m,'LLM_KEY','');self.key.start()
 def tearDown(self):self.key.stop()
 def chat(self,text,**kw):return self.client.post('/api/chat',json={'message':text,**kw}).json
 def test_explicit_item_in_multi_item_order(self):
  d=self.chat('订单 Anker009 里有 X10 Pro 和 C10，我要问 C10。')
  self.assertIn('C10',d['trace']['product']);self.assertNotIn('X10',d['trace']['product'])
 def test_same_name_requires_clarification(self):
  d=self.chat('S1 Pro出了问题',session_id='ambiguity')
  self.assertEqual(d['trace']['product_state'],'CONFLICTED')
  d=self.chat('是吸奶器',session_id='ambiguity')
  self.assertIn('吸奶',d['trace']['product'])
 def test_multilingual_intent_and_language(self):
  d=self.chat('Uw bestelling Anker006 is al verzonden. Deze is nog steeds niet binnen!',language='nl')
  self.assertEqual(d['trace']['response_language'],'nl')
  self.assertIn('Anker1234567-8',d['reply'])
  d=self.chat('Produktname: X10 Pro Omni Produktnummer: T2351 Fehlercode: 2111-Die Rollbürste funktioniert nicht richtig.',language='de')
  self.assertEqual(d['trace']['response_language'],'de');self.assertTrue(any(c['kind']=='knowledge' for c in d['citations']))
 def test_dealer_is_catalog_evidence_not_customer_verification(self):
  d=self.chat('我在 US 的 Aeroflow Breastpumps 买的，能确认购买渠道吗？')
  self.assertEqual(d['trace']['dealer'],'AUTHORIZED');self.assertEqual(d['trace']['ownership_status'],'NOT_VERIFIED')
  self.assertIn('购买凭证',d['reply'])
  for c in d['citations']:
   r=self.client.get(c['url']);self.assertEqual(r.status_code,200);r.close()
  d=self.chat('Aeroflow Breastpumps渠道能确认吗？',session_id='missing-country')
  self.assertNotEqual(d['trace']['dealer'],'AUTHORIZED')
 def test_safety_and_shipping_conflict_offline(self):
  d=self.chat('T8D04 burned me',language='en');self.assertIn('stop using',d['reply'])
  d=self.chat('Anker002 UPS Anker1234567-3 label has been created but I have not received it.',language='en')
  self.assertIn('conflict',d['reply']);self.assertNotIn('Please share the full tracking',d['reply'])
 def test_usage_and_concrete_fault_not_overwritten_by_strategy(self):
  d=self.chat('T8D04 吸奶器如何设置自定义吸乳节奏？')
  self.assertIn('b-2',[c['id'] for c in d['citations']])
  d=self.chat('T8D04 motor making awful noise. Can I get a replacement?',language='en')
  self.assertTrue({'b-37','b-124'} & {c['id'] for c in d['citations']})
 def test_emotion_and_code_boundaries(self):
  for text in ['You’re fucking cameras suck','This app is shit','I am furious']:
   self.assertEqual(customer_signals.emotion(text),'ANGRY');self.assertGreaterEqual(customer_signals.emotion_score(text),7)
  self.assertEqual(customer_signals.emotion('Hello, please help'),'NORMAL')
  self.assertEqual(attribution.extract_error_codes('Probleemcode: 3212; Fehlercode: 3212'),['3212'])
  self.assertEqual(attribution.extract_error_codes('Problem Code: 21073321 EB1L: water error'),['EB1L'])
  self.assertEqual(attribution.extract_error_codes('E25 E28 T2351 2026 Anker1234567'),[])
 def test_negative_execution_sentence_is_allowed_positive_rejected(self):
  refs=[{'id':'service-rules','kind':'context'}]
  def run(sentence):
   return grounded_response.generate(lambda *a,**kw:json.dumps({'reply':'I understand.\n\n'+sentence+'\n\nPlease provide proof of purchase.','source_ids':['service-rules']}),'refund','en',{},'',refs,[],[],[],'chat')
  self.assertIsNotNone(run('No refund has been issued.'))
  self.assertIsNone(run('Your refund has been issued.'))
  self.assertIsNone(run('No refund has been issued. Your replacement was sent.'))
 def test_tone_forwarded_and_fields_protected(self):
  seen=[]
  def call(system,user,**kw):
   payload=json.loads(user);seen.append(payload)
   return json.dumps({'text':'I understand the inconvenience. Order Anker002 requires review. [1]'})
  d=mail_editing.rewrite(call,'Order Anker002 requires review. [1]','tone','en','empathetic')
  self.assertEqual(seen[0]['tone'],'empathetic');self.assertIn('[1]',d['text'])
  with self.assertRaises(ValueError):mail_editing.rewrite(call,'Order Anker003 [1]','tone','en','formal')
 def test_damaged_pin_is_review_not_generic_charging(self):
  d=self.chat('T8D04 one pin is jammed or broken and no longer charges despite cleaning',language='en')
  self.assertEqual(d['trace']['answer_route'],'HUMAN_REVIEW')
  self.assertIn('Do not manipulate',d['reply']);self.assertIn('photo',d['reply'])
  self.assertNotIn('12 seconds',d['reply'])
 def test_tray_condition_not_applied_before_latch_confirmation(self):
  d=self.chat('T2351 water tray will not empty. I have already cleaned it and checked the hose.',language='en')
  self.assertIn('latch',d['reply']);self.assertNotIn('pull',d['reply'])
  self.assertEqual([c['id'] for c in d['citations']],['r-255'])
 def test_expired_warranty_cannot_be_rewritten_as_valid(self):
  d=self.chat('Anker014 还在保修期吗，可以退款吗？',language='zh')
  self.assertEqual(d['trace']['warranty'],'EXPIRED');self.assertIn('已过保',d['reply'])
  refs=[{'id':'service-rules','kind':'context'}]
  out=grounded_response.generate(lambda *a,**kw:json.dumps({'reply':'我来核对。\n\n质保日期在有效范围。\n\n请提供凭证。','source_ids':['service-rules']}),'质保','zh',{'warranty':'EXPIRED'},'',refs,[],[],[],'chat')
  self.assertIsNone(out)
