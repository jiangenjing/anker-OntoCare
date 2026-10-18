import unittest
from unittest.mock import patch
import app as runtime
import judge_server
from ontocare_multimodal import model, resources


class JudgeDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.client = judge_server.app.test_client()

    def test_public_readonly_model_status_works_with_a_server_configured_key(self):
        with patch.object(runtime, 'LLM_KEY', 'judge-test-key'), patch.object(runtime, 'VLM_KEY', 'judge-test-key'):
            response = self.client.get('/api/models', base_url='https://judges.example')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('judge-test-key', response.get_data(as_text=True))

    def test_public_multimodal_request_keeps_the_existing_adapter(self):
        with patch.object(runtime, 'LLM_KEY', 'judge-test-key'), patch.object(runtime, 'VLM_KEY', 'judge-test-key'), patch.object(resources, 'run', return_value={'status': 'OK', 'text': 'test'}) as run:
            response = self.client.post('/api/models', base_url='https://judges.example', headers={'Origin': 'https://judges.example'}, json={'operation': 'test', 'model_id': 'nova'})
        self.assertEqual(response.status_code, 200)
        run.assert_called_once_with({'operation': 'test', 'model_id': 'nova'})

    def test_public_deployment_does_not_open_local_maintenance(self):
        for path, body in [('/api/models', {'action': 'configure', 'api_key': 'other'}), ('/api/benchmark/run', {})]:
            self.assertEqual(self.client.post(path, base_url='https://judges.example', json=body).status_code, 404)
        self.assertEqual(self.client.get('/api/benchmark/status').status_code, 404)

    def test_cross_origin_writes_are_rejected_before_a_model_request(self):
        with patch.object(resources, 'run') as run:
            response = self.client.post('/api/models', base_url='https://judges.example', headers={'Origin': 'https://elsewhere.example'}, json={'operation': 'test', 'model_id': 'nova'})
        self.assertEqual(response.status_code, 403)
        run.assert_not_called()

    def test_health_requires_a_configured_connection_without_returning_the_key(self):
        with patch.dict(model.CONFIG, {'api_key': 'judge-test-key'}):
            response = self.client.get('/api/judge-health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'ready')
        self.assertNotIn('judge-test-key', response.get_data(as_text=True))
        with patch.dict(model.CONFIG, {'api_key': ''}):
            self.assertEqual(self.client.get('/api/judge-health').status_code, 503)

    def test_customer_and_merchant_pages_remain_available(self):
        for path in ['/', '/merchant']:
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)
                self.assertIn('judge-demo.css', response.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
