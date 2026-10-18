import unittest
import app as m

class DatasetTests(unittest.TestCase):
    def setUp(self):
        m.LLM_KEY = ''
        m.SESSIONS.clear()
        self.client = m.app.test_client()

    def test_counts_and_continuation_rows(self):
        self.assertEqual(m.DATA_SUMMARY, dict(tickets=63, orders=16, order_rows=24,
            knowledge=875, visible_knowledge=872, dealers=336, source_file='黑客松智能服务赛题资料.xlsx'))
        self.assertEqual(len(m.ORDERS['ANKER002']['items']), 2)
        self.assertEqual(m.lookup_order('Anker002')['warranty'], 'UNKNOWN')
        self.assertEqual(m.lookup_order('Anker002', 'T2080GA1')['order']['sku'], 'T2080GA1')

    def test_visibility_and_product_scope(self):
        self.assertFalse(any(k['source_sheet']=='eufy Breast Pump Q&A' and k['source_row'] in [184,185,268] for k in m.KB_LIST))
        for pn in ['T2080','T8D04']:
            result=m.match_fault(pn, "won't turn on cannot power on")
            self.assertIsNotNone(result)
            self.assertEqual(result['product_id'],pn)
        self.assertIsNone(m.match_fault('E2353','cannot power on'))

    def test_all_tickets_run(self):
        for t in m.TICKETS:
            r=self.client.post('/api/chat',json={'message':t['客户首封邮件内容'], 'ticket_row':t['原文行号'],
                'order_id':t['订单号'] if t['订单号'].startswith('Anker') else None,'new_case':True})
            self.assertEqual(r.status_code,200,t['原文行号'])
            self.assertNotIn('direct_refund',r.json['trace']['allowed'])

    def test_shipping_preserves_both_rows(self):
        r=self.client.post('/api/chat',json={'message':'Anker002 where is my shipment?'})
        self.assertEqual(r.json['trace']['order_status'],'FOUND')
        self.assertEqual(len(r.json['cards']),2)
        self.assertEqual(r.json['trace']['dealer'],'INSUFFICIENT_INFO')

    def test_dealers_and_data_endpoint(self):
        self.assertEqual(self.client.get('/api/dealer?country=US&seller=best%20buy').json['status'],'AUTHORIZED')
        self.assertEqual(self.client.get('/api/dealer?country=US&seller=unknown').json['status'],'NO_MATCH')
        self.assertEqual(len(self.client.get('/api/data').json['tickets']),63)

    def test_ticket_sku_not_overridden_by_tracking_word(self):
        t=m.TICKETS[1]
        r=self.client.post('/api/chat',json={'message':t['客户首封邮件内容'],'ticket_row':t['原文行号'],'order_id':t['订单号']})
        self.assertEqual(r.json['trace']['warranty'],'VALID')
        self.assertEqual(r.json['trace']['product'],'S1 Pro 扫地机')
