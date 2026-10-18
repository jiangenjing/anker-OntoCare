import unittest
import app as m

class ShippingConversation(unittest.TestCase):
    def setUp(self):
        m.LLM_KEY = ''
        m.SESSIONS.clear()
        self.client = m.app.test_client()

    def ask(self, text, **kw):
        r = self.client.post('/api/chat', json={'message': text, 'session_id': 'shipping', **kw})
        self.assertEqual(r.status_code, 200)
        return r.json

    def test_screenshot_followups_keep_shipping_and_order(self):
        t = m.TICKETS[1]
        self.ask(t['客户首封邮件内容'], ticket_row=t['原文行号'], order_id=t['订单号'])
        for question in ['T2080GA1发货了吗', 'T2080GA1', '？？？？']:
            d = self.ask(question)
            self.assertEqual(d['trace']['order'], 'ANKER002')
            self.assertIn('2026-09-18', d['reply'])
            self.assertIn('Anker1234567-2', d['reply'])
            self.assertNotIn('具体症状', d['reply'])
            self.assertEqual(len(d['cards']), 1)

    def test_sku_alone_does_not_identify_customer_order(self):
        for question in ['T2080GA1发货了吗', 'T2080GA1', '？？？？']:
            d = self.ask(question)
            self.assertIn('订单号', d['reply'])
            self.assertNotIn('具体症状', d['reply'])
            self.assertNotIn('2026-09-18', d['reply'])

    def test_shipping_question_then_order_number(self):
        self.ask('我的订单到哪了？')
        d = self.ask('Anker002')
        self.assertIn('Anker1234567-2', d['reply'])
        self.assertIn('Anker1234567-3', d['reply'])
        self.assertEqual(len(d['cards']), 2)

    def test_tracking_number_is_not_truncated_into_order_id(self):
        self.ask('Anker002发货了吗')
        d = self.ask('Anker1234567-3呢')
        self.assertEqual(d['trace']['order'], 'ANKER002')
        self.assertIn('2026-09-20', d['reply'])
        self.assertEqual(len(d['cards']), 1)

    def test_other_sku_must_not_return_previous_shipment(self):
        self.ask('Anker002发货了吗')
        d = self.ask('T2353111发货了吗')
        self.assertNotIn('2026-09-18', d['reply'])
        self.assertIn('订单号', d['reply'])

    def test_can_switch_from_shipping_to_troubleshooting(self):
        self.ask('Anker002发货了吗')
        d = self.ask('T2080GA1无法开机')
        self.assertNotIn('物流记录', d['reply'])
        self.assertEqual(d['trace']['answer_route'], 'FAQ_CACHE')
        self.assertTrue(d['citations'])
