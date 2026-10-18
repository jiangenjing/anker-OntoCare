import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
import fixed_api
from model_demo import register_model_demo
from ontocare_multimodal import model, resources


class FixedApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'demo_api_config.json'
        self.values = {'base_url': fixed_api.DEFAULT_BASE, 'api_key': 'demo-fixed-test-key',
                       'text_model': fixed_api.DEFAULT_TEXT_MODEL, 'vision_model': fixed_api.DEFAULT_VISION_MODEL}
        self.path.write_text(json.dumps(self.values))
        self.previous = dict(model.CONFIG)

    def tearDown(self):
        model.CONFIG.clear()
        model.CONFIG.update(self.previous)
        self.folder.cleanup()

    def client(self):
        runtime = fixed_api.load(self.path, {})
        app = Flask(__name__, static_folder=str(Path(__file__).resolve().parents[1] / 'static'), static_url_path='')
        register_model_demo(app, runtime)
        return app.test_client(), runtime

    def test_fixed_file_wins_over_stale_environment_and_restores_on_each_start(self):
        stale = {'LLM_API_KEY': 'old-env-key', 'LLM_MODEL': 'other-model'}
        first = fixed_api.load(self.path, stale)
        second = fixed_api.load(self.path, {})
        self.assertEqual(first, second)
        self.assertTrue(first['FIXED_CONNECTION'])
        self.assertEqual(first['LLM_KEY'], self.values['api_key'])
        self.assertEqual(first['VLM_KEY'], first['LLM_KEY'])
        self.assertEqual(first['LLM_MODEL'], fixed_api.DEFAULT_TEXT_MODEL)
        self.assertEqual(first['VLM_MODEL'], fixed_api.DEFAULT_VISION_MODEL)

    def test_startup_connects_both_main_models_and_the_shared_capability_gateway(self):
        client, runtime = self.client()
        self.assertEqual(resources.gateway(), (fixed_api.DEFAULT_BASE, self.values['api_key']))
        self.assertEqual(model.CONFIG['model'], runtime['LLM_MODEL'])
        self.assertEqual(model.CONFIG['vision_model'], runtime['VLM_MODEL'])
        data = client.get('/api/models').get_json()
        self.assertTrue(data['catalog']['configured'])
        self.assertTrue(data['config']['configured'])
        self.assertTrue(data['config']['vision_configured'])
        self.assertTrue(data['config']['connection_locked'])
        self.assertEqual(data['config']['key_storage'], 'SERVER_FILE')
        self.assertNotIn(self.values['api_key'], json.dumps(data))

    def test_web_configuration_cannot_replace_the_fixed_judging_connection(self):
        client, runtime = self.client()
        response = client.post('/api/models', json={'action': 'configure', 'api_key': 'another-test-key'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(runtime['LLM_KEY'], self.values['api_key'])

    def test_backend_config_is_not_exposed_as_a_static_asset(self):
        client, _ = self.client()
        self.assertEqual(client.get('/demo_api_config.json').status_code, 404)
        self.assertEqual(client.get('/fixed_api.py').status_code, 404)
        with client.get('/merchant.html') as response:
            html = response.get_data(as_text=True)
        self.assertNotIn('id="modelSettings"', html)
        self.assertNotIn('data-workspace-tab="models"', html)
        self.assertNotIn('model-settings.js', html)

    def test_malformed_key_or_config_does_not_echo_credentials(self):
        for value in [None, 'Bearer demo-fixed-test-key', 'demo-fixed-test-key\n']:
            self.values['api_key'] = value
            self.path.write_text(json.dumps(self.values))
            with self.assertRaises(ValueError) as raised:
                fixed_api.load(self.path, {})
            self.assertNotIn('demo-fixed-test-key', str(raised.exception))
        self.path.write_text('{invalid-json')
        with self.assertRaises(ValueError):
            fixed_api.load(self.path, {})

    def test_legacy_environment_still_works_without_a_fixed_file(self):
        runtime = fixed_api.load(Path(self.folder.name) / 'missing.json', {'COMPETITION_API_KEY': 'legacy-test-key'})
        self.assertEqual(runtime['LLM_KEY'], 'legacy-test-key')
        self.assertEqual(runtime['VLM_KEY'], 'legacy-test-key')
        self.assertFalse(runtime['FIXED_CONNECTION'])

    def test_release_collector_includes_the_preconfigured_backend_file(self):
        from scripts.package_release import collect
        self.assertIn('demo_api_config.json', {str(file.relative_to(Path(__file__).resolve().parents[1])) for file in collect()})


if __name__ == '__main__':
    unittest.main()
