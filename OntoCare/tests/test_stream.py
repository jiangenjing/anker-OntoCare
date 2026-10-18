import json
import unittest
import app as m

class StreamTests(unittest.TestCase):
    def setUp(self):
        m.LLM_KEY = ''
        m.SESSIONS.clear()
        self.client = m.app.test_client()

    def test_progress_then_result(self):
        response=self.client.post('/api/chat/stream',json={'message':'Anker002 T2080GA1发货了吗'})
        events=[json.loads(line) for line in response.data.splitlines()]
        self.assertTrue(all(e['type']=='progress' for e in events[:-1]))
        self.assertEqual(events[-1]['type'],'result')
        self.assertEqual(events[-1]['status'],200)
        self.assertIn('2026-09-18',events[-1]['data']['reply'])
        self.assertTrue(any('已找到订单' in e.get('text','') for e in events))

    def test_invalid_input_ends_stream(self):
        response=self.client.post('/api/chat/stream',json={'message':''})
        event=json.loads(response.data)
        self.assertEqual(event['type'],'result')
        self.assertEqual(event['status'],400)

    def test_ontology_step_references_resolve_without_changing_answer(self):
        request={'message':'Anker002 T2080GA1发货了吗','session_id':'step-citations'}
        response=self.client.post('/api/chat/stream',json=request)
        events=[json.loads(line) for line in response.data.splitlines()]
        progress=events[:-1]
        self.assertTrue(all(isinstance(e.get('citations'),list) for e in progress))
        references=[c for e in progress for c in e['citations']]
        self.assertEqual({c['type'] for c in references},{'ServiceOntology','DecisionOntology','Ontology'})
        from urllib.parse import urlsplit
        for c in references:
            self.assertTrue(c['label']);self.assertTrue(c['detail'])
            url=urlsplit(c['uri']);self.assertFalse(url.netloc)
            page=self.client.get(url.path)
            self.assertEqual(page.status_code,200)
            self.assertIn('id="'+url.fragment+'"',page.get_data(as_text=True))
            page.close()
        ordinary=self.client.post('/api/chat',json={**request,'session_id':'ordinary-citations'}).json
        self.assertEqual(events[-1]['data']['reply'],ordinary['reply'])
        self.assertEqual(events[-1]['data']['citations'],ordinary['citations'])

    def test_steps_without_ontology_reference_remain_unannotated(self):
        from flask import g
        events=[]
        with m.app.test_request_context():
            g.progress=events.append;g.progress_language='zh'
            m.report_progress('正在返回答复','Returning response')
        self.assertEqual(events[0]['citations'],[])

    def test_english_step_reference_labels_follow_conversation(self):
        response=self.client.post('/api/chat/stream',json={'message':'Where is my order Anker002? Please check shipping.','language':'auto'})
        events=[json.loads(line) for line in response.data.splitlines()]
        for step in events[:-1]:
            self.assertEqual(step['language'],'en')
            for c in step['citations']:
                self.assertNotRegex(c['label']+c['detail'],r'[\u4e00-\u9fff]')
