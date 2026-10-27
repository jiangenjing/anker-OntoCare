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
        self.assertNotIn('核对这次的物流问题', reply['reply'])
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

    def test_emotion_in_new_conversation_is_acknowledged(self):
        result = self.ask('我生气了')
        self.assertNotIn('具体产品型号', result['reply'])
        self.assertTrue(any(word in result['reply'] for word in ('生气', '心情', '难受')))
        self.assertEqual(result['trace']['answer_route'], 'CONVERSATION_REPAIR')
        self.assertEqual(len(result['reply'].split('\n\n')), 3)

    def test_emotion_after_shipping_does_not_repeat_shipping(self):
        self.ask('Anker002发货了吗')
        result = self.ask('真的太让人失望了')
        self.assertNotIn('物流记录', result['reply'])
        self.assertIn('失望', result['reply'])
        self.assertIn('物流记录', self.ask('再看看物流')['reply'])

    def test_ambiguous_feedback_uses_model_classification(self):
        self.ask('Anker002发货了吗')
        with patch.object(m, 'LLM_KEY', 'test'), patch.object(m, 'LLM_MODEL', 'test'), \
             patch.object(m, 'call_llm', return_value='{"intent":"feedback"}') as model:
            result = self.ask('你刚才是不是搞错重点了')
        self.assertTrue(model.called)
        self.assertNotIn('物流记录', result['reply'])
        self.assertEqual(result['trace']['answer_route'], 'CONVERSATION_REPAIR')

    def test_model_failure_does_not_guess_old_intent(self):
        self.ask('Anker002发货了吗')
        with patch.object(m, 'LLM_KEY', 'test'), patch.object(m, 'LLM_MODEL', 'test'), \
             patch.object(m, 'call_llm', return_value=None):
            result = self.ask('你刚才是不是搞错重点了')
        self.assertNotIn('物流记录', result['reply'])
        self.assertIn('请', result['reply'])

    def test_business_question_with_emotion_still_uses_business_route(self):
        result = self.ask('我生气了，我的订单 Anker002 到哪了？')
        self.assertIn('物流', result['reply'])
        self.assertNotEqual(result['trace']['answer_route'], 'CONVERSATION_REPAIR')
        self.assertEqual(len(result['reply'].split('\n\n')), 3)

    def test_feedback_with_new_business_request_is_not_ignored(self):
        self.ask('Anker002发货了吗')
        result = self.ask('你没听懂，我现在想退货')
        self.assertNotEqual(result['trace']['answer_route'], 'CONVERSATION_REPAIR')
        self.assertEqual(m.SESSIONS['feedback']['service_intent'], 'return')

    def test_reply_skill_is_part_of_model_prompt(self):
        import customer_reply_skill
        import grounded_response
        self.assertIn('三个部分', customer_reply_skill.INSTRUCTIONS)
        seen = []
        def fake(system, user, timeout=60):
            seen.append(system)
            return None
        grounded_response.generate(fake, '问题', 'zh', {}, '', [], [], [], [], 'chat')
        self.assertIn(customer_reply_skill.INSTRUCTIONS, seen[0])

