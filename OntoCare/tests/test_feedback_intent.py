import unittest
from unittest.mock import patch

import app as m


class FeedbackIntentTests(unittest.TestCase):
    def setUp(self):
        m.SESSIONS.clear()
        self.client = m.app.test_client()
        self.key = patch.object(m, 'LLM_KEY', '')
        self.key.start()
        self.addCleanup(self.key.stop)

    def ask(self, text):
        result = self.client.post('/api/chat', json={'message': text, 'session_id': 'feedback'})
        self.assertEqual(result.status_code, 200)
        return result.get_json()

    def test_complaint_does_not_repeat_previous_shipment(self):
        self.ask('Anker002发货了吗')
        reply = self.ask('你为什么不能听懂我说的话？？')
        self.assertNotIn('物流记录', reply['reply'])
        self.assertNotIn('Anker1234567', reply['reply'])
        self.assertEqual(reply['trace']['answer_route'], 'CONVERSATION_REPAIR')
        self.assertFalse(any(c['kind'] == 'order' for c in reply['citations']))
        self.assertIn('抱歉', reply['reply'])
        self.assertIn('shipping', m.SESSIONS['feedback']['service_intent'])
        self.assertIn('物流记录', self.ask('再看看物流')['reply'])

    def test_english_complaint_gets_english_repair(self):
        self.ask('Where is my order Anker002?')
        reply = self.ask("Why don't you understand what I said?")
        self.assertEqual(reply['trace']['answer_route'], 'CONVERSATION_REPAIR')
        self.assertIn('sorry', reply['reply'].lower())
        self.assertNotIn('Anker1234567', reply['reply'])

    def test_shipping_complaint_still_answers_shipping(self):
        self.ask('Anker002发货了吗')
        result = self.ask('为什么物流这么慢？')
        self.assertIn('物流', result['reply'])
        self.assertNotEqual(result['trace']['answer_route'], 'CONVERSATION_REPAIR')

