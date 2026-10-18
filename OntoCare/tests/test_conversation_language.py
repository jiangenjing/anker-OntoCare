import json
import re
import unittest
from unittest.mock import patch
import app as m
import customer_signals
import followup_questions

class ConversationLanguageTests(unittest.TestCase):
    def setUp(self):
        m.SESSIONS.clear()
        self.client=m.app.test_client()
        self.key=patch.object(m,'LLM_KEY','');self.key.start()
    def tearDown(self):self.key.stop()
    def ask(self,text,**kw):
        response=self.client.post('/api/chat',json={'message':text,'session_id':'language-switch','language':'auto',**kw})
        self.assertEqual(response.status_code,200)
        return response.json
    def test_switch_and_neutral_turns_keep_session_language(self):
        for text,lang in [('订单发货了吗？','zh'),('Where is my order?','en'),('Anker002','en'),('T2080GA1','en'),('???','en'),('我还没收到包裹','zh'),('Anker002','zh')]:
            result=self.ask(text)
            self.assertEqual(result['response_language'],lang,text)
            self.assertEqual(result['followups']['language'],lang)
            self.assertEqual(result['trace']['response_language'],lang)
        self.assertEqual(self.client.get('/api/session/language-switch').json['response_language'],'zh')
    def test_short_english_and_model_only_input(self):
        for text in ['Hello','Thanks','Yes','Help','Next']:
            self.assertEqual(customer_signals.language(text,'auto','zh'),'en')
        for text in ['S1 Pro','T2080GA1','6011','Anker002','???']:
            self.assertEqual(customer_signals.language(text,'auto','en'),'en')
            self.assertEqual(customer_signals.language(text,'auto','zh'),'zh')
    def test_chinese_knowledge_questions_keep_codes_and_sources(self):
        result=self.ask('T2280 错误码4020怎么办？')
        for q in result['followups']['questions']:
            self.assertRegex(q['text'],r'[\u4e00-\u9fff]')
            self.assertNotRegex(q['text_en'],r'[\u4e00-\u9fff]')
            self.assertTrue(q['source_ids'])
        zh,en=followup_questions.localized_title('What should I do if Omni C20 T2280 reports error 6012/6013: Sprinkler error?','T2280','r-test')
        self.assertIn('6012/6013',zh);self.assertIn('应该如何排查',zh)
    def test_progress_language_matches_reply(self):
        self.ask('Where is my order?')
        r=self.client.post('/api/chat/stream',json={'message':'Anker002','session_id':'language-switch','language':'auto'})
        events=[json.loads(line) for line in r.data.splitlines()]
        for e in events[:-1]:
            self.assertEqual(e['language'],'en');self.assertNotRegex(e['text'],r'[\u4e00-\u9fff]')
        self.assertEqual(events[-1]['data']['response_language'],'en')
    def test_workflow_language_switch_preserves_progress(self):
        self.ask('T2080 EB1L 加水故障')
        d=self.ask('Please explain step 1.')
        self.assertIn('clean-water tank',d['reply']);self.assertNotRegex(d['reply'],r'[\u4e00-\u9fff]')
        d=self.ask('下一步')
        self.assertIn('第 2 步',d['reply']);self.assertIn('进水口',d['reply'])
        self.assertEqual(m.SESSIONS['language-switch']['active_workflow']['cursor'],1)
    def test_new_case_resets_language(self):
        self.ask('Where is my order?')
        self.assertEqual(self.ask('Anker002',new_case=True)['response_language'],'zh')
    def test_cached_workflow_switch(self):
        self.ask('T8D04 吸力很弱')
        d=self.ask('Please explain step 1.')
        self.assertEqual(d['response_language'],'en');self.assertNotRegex(d['reply'],r'[\u4e00-\u9fff]')
    def test_guard_rejects_wrong_generated_language(self):
        self.assertFalse(customer_signals.reply_matches_language('Please check the model.','zh'))
        self.assertFalse(customer_signals.reply_matches_language('请检查型号。','en'))
        self.assertTrue(customer_signals.reply_matches_language('请确认 S1 Pro 型号 T2080。','zh'))

    def test_unaligned_translation_does_not_reinterpret_step_cursor(self):
        self.ask('T8D04 weak suction, please help')
        flow=m.SESSIONS['language-switch']['active_workflow']
        flow['cursor']=len(flow['steps'])-1
        cursor=flow['cursor']
        d=self.ask('下一步')
        self.assertEqual(d['response_language'],'zh')
        self.assertIn('暂不推进',d['reply'])
        self.assertEqual(flow['cursor'],cursor)

    def test_chinese_prose_with_english_product_changes_previous_english(self):
        self.ask('Where is my order?')
        result=self.ask('我的产品是 Omni E25，型号 T2353')
        self.assertEqual(result['response_language'],'zh')
        self.assertRegex(result['reply'],r'[\u4e00-\u9fff]')
        for q in result['followups']['questions']:
            self.assertRegex(q['text'],r'[\u4e00-\u9fff]')
            self.assertTrue(q['source_ids'])
    def test_product_name_and_source_english_do_not_override_chinese(self):
        for text in ['eufy S1 Pro Breast Pump','Omni E25','SoloCam S340','我的 Omni E25 显示 offline, please help']:
            self.assertEqual(customer_signals.language(text,'auto','zh'),'zh',text)
    def test_recommended_question_describes_original_symptom(self):
        for title,expected in [('What if Omni E25 does not perform base station tasks such as dust collection?', '基站'),('Omni E25 stuck on rug','地毯'),('Omni E25 always shows offline','离线'),("Omni E25 can\'t connect to wifi",'Wi-Fi')]:
            zh,en=followup_questions.localized_title(title,'T2353','r-2')
            self.assertIn(expected,zh);self.assertEqual(en,title)
