import json
import unittest
from unittest.mock import patch
from flask import g
import app as m
import qa_workflows as qa

QUESTIONS = {'power':'无法开机', 'charge':'充不上电', 'case_charge':'充电盒不充电', 'suction':'吸力很弱',
 'wifi':'wifi连不上', 'app_connect':'App连不上', 'milk_leak':'漏奶', 'dishwasher':'可以用洗碗机吗',
 'microwave':'可以用微波炉消毒吗', 'recording':'支持连续录像吗', 'usb_charge':'USB不充电',
 'solar_charge':'太阳能不充电', 'offline':'显示离线', 'dock_7033':'错误码7033', 'error_2310':'错误码2310', 'error_7031':'错误码7031'}

class FAQTests(unittest.TestCase):
    def setUp(self):
        m.SESSIONS.clear()
        self.client=m.app.test_client()

    def ask(self, message, **extra):
        r=self.client.post('/api/chat',json={'message':message,'new_case':True,**extra})
        self.assertEqual(r.status_code,200)
        return r.json

    def test_all_reviewed_keys_skip_llm_even_when_configured(self):
        with patch.object(m,'GROUNDED_MODE',True), patch.object(m,'LLM_KEY','test-key'), patch.object(m,'LLM_MODEL','test-model'), patch.object(m,'call_llm') as llm:
            for entry in qa.CACHE['entries']:
                for lang in ('zh','en'):
                    d=self.ask(entry['pn']+' '+QUESTIONS[entry['topic']],language=lang)
                    self.assertEqual(d['trace']['answer_route'],'FAQ_CACHE',(entry['pn'],entry['topic'],d['reply']))
                    self.assertEqual(d['trace']['model_calls'],0)
                    self.assertTrue(d['citations'])
                    for c in d['citations']:
                        self.assertEqual(self.client.get(c['url']).status_code,200)
            llm.assert_not_called()

    def test_ambiguous_product_does_not_use_cache(self):
        with patch.object(m,'call_llm') as llm:
            d=self.ask('S1 Pro无法开机')
            self.assertNotEqual(d['trace']['answer_route'],'FAQ_CACHE')
            self.assertIn('吸奶器',d['reply'])
            llm.assert_not_called()

    def test_conflict_does_not_choose_one_source(self):
        with patch.object(m,'call_llm') as llm:
            d=self.ask('T2080序列号在哪')
            self.assertEqual(d['trace']['answer_route'],'SOURCE_CONFLICT')
            self.assertEqual(len(d['citations']),2)
            llm.assert_not_called()

    def test_invisible_sources_are_not_served(self):
        for sid in ('b-184','b-185','b-268'):
            self.assertEqual(self.client.get('/api/sources/'+sid).status_code,404)

    def test_changed_source_invalidates_fixed_answer(self):
        with patch.dict(qa.SOURCES['b-54'],{'Content':'changed content'}):
            self.assertIsNone(qa.cached_answer('T8D04','无法开机','zh'))

    def test_risk_and_multi_issue_are_not_cached(self):
        self.assertIsNone(qa.cached_answer('T8D04','吸力很弱而且出血','zh'))
        self.assertIsNone(qa.cached_answer('T2353','wifi连不上同时充不上电','zh'))
        self.assertIsNone(qa.cached_answer('T2351','支持WiFi6吗','zh'))

    def test_long_tail_model_and_sources(self):
        refs=qa.retrieve('T2080','T2080固件更新失败')
        self.assertTrue(refs)
        def generated(*args,**kwargs):
            g.model_status='OK';g.model_calls+=1
            payload=json.loads(args[1]);self.assertEqual(payload['product'],'T2080')
            return json.dumps({'reply':'请先核对重置操作及设备型号。','source_ids':[refs[0]]})
        with patch.object(m,'LLM_KEY','test-key'), patch.object(m,'LLM_MODEL','test-model'), patch.object(m,'call_llm',side_effect=generated) as llm:
            d=self.ask('T2080固件更新失败')
            self.assertEqual(d['trace']['answer_route'],'GROUNDED_LLM')
            self.assertEqual(d['trace']['model_calls'],1)
            self.assertEqual(d['citations'][0]['id'],refs[0])
            llm.assert_called_once()

    def test_invalid_model_citation_falls_back_to_source(self):
        with patch.object(m,'LLM_KEY','test-key'), patch.object(m,'LLM_MODEL','test-model'), patch.object(m,'call_llm',return_value='{"reply":"invented", "source_ids":["fake"]}'):
            d=self.ask('T2080固件更新失败')
            self.assertEqual(d['trace']['answer_route'],'SOURCE_FALLBACK')
            self.assertNotIn('invented',d['reply'])
            self.assertTrue(d['citations'])

    def test_model_error_preserves_cited_fallback(self):
        def broken(*args,**kwargs):
            g.model_status='ERROR';g.model_calls+=1
            return None
        with patch.object(m,'LLM_KEY','test-key'), patch.object(m,'LLM_MODEL','test-model'), patch.object(m,'call_llm',side_effect=broken):
            d=self.ask('T2080固件更新失败')
            self.assertEqual(d['model_status'],'ERROR')
            self.assertEqual(d['trace']['answer_route'],'SOURCE_FALLBACK')

    def test_stream_cache_hit_is_real_progress(self):
        response=self.client.post('/api/chat/stream',json={'message':'T8D04吸力很弱'})
        events=[json.loads(line) for line in response.data.splitlines()]
        self.assertTrue(any('无需调用模型' in e.get('text','') for e in events))
        self.assertTrue(events[-1]['data']['citations'])
