import unittest
from unittest.mock import patch
from flask import Flask
from model_demo import register_model_demo
from ontocare_multimodal import model, resources

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.previous=dict(model.CONFIG)
        self.runtime=dict(LLM_BASE=resources.BASE,LLM_MODEL='hackathon/v_model/nova-pro',LLM_KEY='',VLM_BASE=resources.BASE,VLM_MODEL='hackathon/v_model/deepseek-v4.1-flash',VLM_KEY='')
        app=Flask(__name__);register_model_demo(app,self.runtime);self.client=app.test_client()
        model.CONFIG['gateway_api_key']=''
    def tearDown(self):
        model.CONFIG.clear();model.CONFIG.update(self.previous)
    def test_shared_config_no_secret_response(self):
        r=self.client.post('/api/models',json={'action':'configure','api_key':'demo-test-key'})
        self.assertEqual(r.status_code,200)
        self.assertNotIn('demo-test-key',r.get_data(as_text=True))
        self.assertEqual(self.runtime['LLM_KEY'],'demo-test-key')
        self.assertEqual(self.runtime['VLM_KEY'],'demo-test-key')
    def test_external_and_cross_origin_denied(self):
        self.assertEqual(self.client.get('/api/models',environ_base={'REMOTE_ADDR':'10.0.0.1'}).status_code,403)
        self.assertEqual(self.client.post('/api/models',json={},headers={'Origin':'https://example.com'}).status_code,403)
    def test_catalog_and_missing_key(self):
        self.assertEqual(len(self.client.get('/api/models').json['catalog']['models']),9)
        r=self.client.post('/api/models',json={'model_id':'nova','operation':'text','text':'hi'})
        self.assertEqual(r.json['status'],'NOT_CONFIGURED')
    def test_tts_path_and_header(self):
        with patch.object(resources,'_send',return_value=({'output':{'audio':{'url':'https://example.com/a.wav'}}},{'status':'OK'})) as send:
            resources.run({'model_id':'tts','operation':'tts','text':'你好'})
        self.assertEqual(send.call_args.args[0],'/openai_passthrough/services/audio/tts/SpeechSynthesizer')
        self.assertEqual(send.call_args.args[2],{'x-model-provider':'dashscope_ audio'})
    def test_chat_path_and_id(self):
        with patch.object(resources,'_send',return_value=({'choices':[{'message':{'content':'ok'}}]},{'status':'OK'})) as send:
            resources.run({'model_id':'nova','operation':'text','text':'hi'})
        self.assertEqual(send.call_args.args[0],'/chat/completions')
        self.assertEqual(send.call_args.args[1]['model'],'hackathon/v_model/nova-pro')
if __name__=='__main__':unittest.main()
