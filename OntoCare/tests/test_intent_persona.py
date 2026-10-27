import unittest
from unittest.mock import patch
import app as m
import intent_router
import customer_reply_skill


class IntentPersonaTests(unittest.TestCase):
    def setUp(self):
        m.SESSIONS.clear()
        self.client = m.app.test_client()
        self.key = patch.object(m, 'LLM_KEY', '')
        self.key.start()
        self.addCleanup(self.key.stop)

    def ask(self, text):
        result = self.client.post('/api/chat', json={'message': text, 'session_id': 'persona-audit'})
        self.assertEqual(result.status_code, 200)
        return result.get_json()

    def test_eight_expression_styles_are_per_turn_not_personality(self):
        examples = {'upset':'我生气了', 'urgent':'请尽快回复', 'benefit':'需要多少费用',
                    'technical':'故障码 6011', 'reasoned':'请解释依据', 'detailed':'请详细说明',
                    'gentle':'谢谢你的帮助', 'unclear':'我不确定怎么做'}
        for expected, text in examples.items():
            with self.subTest(style=expected):
                self.assertEqual(intent_router.identify(text)['style'], expected)
        self.assertEqual(intent_router.identify('好的')['style'], 'neutral')

    def test_style_guides_change_delivery_without_changing_facts(self):
        styles = ['upset', 'urgent', 'benefit', 'technical', 'reasoned', 'detailed', 'gentle', 'unclear']
        openings = set()
        for style in styles:
            emotion = 'ANGRY' if style == 'upset' else 'NORMAL'
            reply = customer_reply_skill.format_reply('仅可核查，尚未退款。', 'zh', emotion, 'WORKFLOW', 'return', style)
            self.assertIn('仅可核查，尚未退款。', reply)
            self.assertNotIn('已退款', reply)
            openings.add(reply.split('\n\n')[0])
        self.assertEqual(len(openings), 8)

    def test_style_resets_to_neutral_on_new_turn(self):
        first = self.ask('我生气了')
        self.assertEqual(first['trace']['intent_router']['style'], 'upset')
        second = self.ask('好的')
        self.assertEqual(second['trace']['intent_router']['style'], 'neutral')

    def test_return_switch_and_proof_followup(self):
        self.ask('Anker002发货了吗')
        result = self.ask('你没听懂，我现在想退货')
        self.assertEqual(result['trace']['intent_router']['intent'], 'return')
        self.assertIn('退', result['reply'])
        self.assertNotIn('请告诉我具体产品型号和问题', result['reply'])
        follow = self.ask('需要什么凭证？')
        self.assertEqual(follow['trace']['intent_router']['intent'], 'return_proof')
        self.assertIn('凭证', follow['reply'])

    def test_model_help_and_capabilities(self):
        result = self.ask('我不知道型号')
        self.assertIn('订单', result['reply'])
        result = self.ask('你能怎么帮我？')
        self.assertIn('物流', result['reply'])
        self.assertNotIn('具体产品型号和问题', result['reply'])

    def test_style_changes_tone_not_refund_authority(self):
        result = self.ask('请尽快退款，我需要补偿')
        self.assertEqual(result['trace']['intent_router']['intent'], 'return')
        self.assertNotIn('已退款', result['reply'])
        self.assertNotIn('已批准', result['reply'])

    def test_safety_overrides_style_and_request(self):
        result = self.ask('急！机器冒烟了我要退款')
        self.assertIn('停止使用', result['reply'])
        self.assertNotIn('已退款', result['reply'])

    def test_negated_return_does_not_override_shipping(self):
        result = self.ask('我不想退货，我要查 Anker002 物流')
        self.assertEqual(result['trace']['intent_router']['intent'], 'shipping')
        self.assertIn('物流', result['reply'])
