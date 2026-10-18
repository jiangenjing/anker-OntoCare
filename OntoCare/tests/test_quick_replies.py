import unittest
import app as m
import quick_replies as q

class QuickRepliesTests(unittest.TestCase):
 def setUp(self):
  m.SESSIONS.clear();self.c=m.app.test_client()
 def ask(self,text):return self.c.post('/api/chat',json={'session_id':'quick','message':text}).json
 def test_channel_question_has_answers(self):
  options=q.choices({},'那这笔是在哪个渠道买的——官方店铺，还是其他平台/商家？')
  self.assertEqual(len(options),3)
  self.assertTrue(all(x['text'] in q.CHANNELS for x in options))
 def test_workflow_buttons_advance_and_resolve(self):
  first=self.ask('T8D04吸力很弱');options=q.choices(m.SESSIONS['quick'],'检查后告诉我结果。')
  self.assertEqual(options[0]['text'],'试过了，还是不行')
  self.ask(options[0]['text']);self.assertEqual(m.SESSIONS['quick']['active_workflow']['cursor'],1)
  self.ask(options[1]['text']);self.assertEqual(m.SESSIONS['quick']['active_workflow']['status'],'RESOLVED')
 def test_channel_claim_is_not_authorization(self):
  self.ask('Anker002 我要退款')
  before=m.SESSIONS['quick']['dealer']
  d=self.ask('我是在官方店铺购买的')
  self.assertEqual(m.SESSIONS['quick']['purchase_channel_claim'],'official_claim')
  self.assertEqual(m.SESSIONS['quick']['dealer'],before)
  self.assertIn('不代表已确认官方授权',d['reply'])
  self.assertEqual(self.c.get('/api/session/quick').json['followups'],d['followups'])
 def test_no_invented_order_choices(self):
  options=q.choices({},'请提供订单号')
  self.assertFalse(any('Anker' in o['text'] for o in options))
 def test_ambiguity_has_model_choices(self):
  options=q.choices({'product_state':'CONFLICTED'},'S1 Pro 是哪种产品？')
  self.assertIn('T2080',options[0]['text']);self.assertIn('T8D04',options[1]['text'])

 def test_return_reason_has_direct_answers(self):
  options=q.choices({'service_intent':'return'},'您想退货的原因是什么？')
  self.assertEqual(len(options),3)
  self.assertTrue(all(x['text'].startswith('退货原因：') for x in options))

 def test_current_graph_filters_and_deduplicates_questions(self):
  case={'transcript':[{'role':'user','text':'已经问过的问题'}], 'followups':{
   'ontology':{'revision':4,'nodes':[{'id':'case'},{'id':'r1'},{'id':'r2'}]},
   'questions':[
    {'text':'已经问过的问题','text_en':'Asked','source_ids':['r1']},
    {'text':'T2280 的使用方法需要注意什么？（资料 r1）','text_en':'How to use T2280?','source_ids':['r1']},
    {'text':'T2280 的使用方法需要注意什么？（资料 r2）','text_en':'Using T2280?','source_ids':['r2']},
    {'text':'旧产品问题','text_en':'Stale question','source_ids':['old']}]}}
  options=q.choices(case,'已记录型号。')
  self.assertEqual(len(options),1)
  self.assertEqual(options[0]['node_ids'],['r1'])
  self.assertEqual(options[0]['ontology_revision'],4)
  self.assertNotIn('资料',options[0]['text'])

 def test_each_turn_refreshes_product_and_provenance(self):
  first=self.ask('我的产品是 Omni C20，型号 T2280')
  options=first['followups']['quick_replies']
  self.assertTrue(options)
  self.assertTrue(any('T2280' in o['text'] for o in options))
  nodes={n['id'] for n in first['followups']['ontology']['nodes']}
  self.assertTrue(all(set(o['node_ids'])<=nodes for o in options))
  second=self.ask('My product is the S1 Pro breast pump T8D04')
  self.assertEqual(second['followups']['language'],'en')
  self.assertTrue(second['followups']['quick_replies'])
  self.assertFalse(any('T2280' in o['text_en'] for o in second['followups']['quick_replies']))
  self.assertGreater(second['followups']['ontology']['revision'], first['followups']['ontology']['revision'])
