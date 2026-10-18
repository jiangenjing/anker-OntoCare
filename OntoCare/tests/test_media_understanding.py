import io,json,tempfile,unittest,subprocess,shutil
from pathlib import Path
from unittest.mock import patch
import app as m
import media_understanding as media
class MediaTests(unittest.TestCase):
 def test_not_configured(self):self.assertEqual(media.understand('x','', '', '')['status'],'NOT_CONFIGURED')
 def test_image_request_and_schema(self):
  reply={'description':'Visible robot vacuum','visible_issue':'red light','error_code':'','product_model':'','sku':''}
  response=io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(reply)}}]}).encode())
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a.png';p.write_bytes(b'image')
   with patch('urllib.request.urlopen',return_value=response) as call:
    result=media.understand(p,'https://example.invalid/v1','test','test-model')
    body=json.loads(call.call_args.args[0].data)
    self.assertEqual(body['messages'][1]['content'][1]['type'],'image_url')
    self.assertEqual(result['status'],'OK')
 def test_session_binding_and_media_to_retrieval(self):
  m.SESSIONS.clear();m.VISION_CACHE['test.png']={'session_id':'media','status':'OK','evidence':{'visible_issue':'吸力很弱','description':'吸奶器吸力弱','error_code':''},'coverage':'single_image'}
  c=m.app.test_client()
  self.assertEqual(c.post('/api/chat',json={'session_id':'other','message':'看图','image':'uploaded:test.png'}).status_code,400)
  with patch.object(m,'LLM_KEY',''):
   c.post('/api/chat',json={'session_id':'media','message':'我的产品是 T8D04'})
   d=c.post('/api/chat',json={'session_id':'media','message':'帮我看图','image':'uploaded:test.png'}).json
  self.assertEqual(d['trace']['image'],'OK');self.assertTrue(d['trace']['media_evidence']);self.assertTrue(any(s['kind']=='knowledge' for s in d['citations']))
 def test_unknown_product_media_gets_contextual_followup(self):
  m.SESSIONS.clear()
  m.VISION_CACHE['unknown.png']={'session_id':'unknown-media','status':'OK','evidence':{'visible_issue':'绿色灯亮','description':'型号不可辨认','error_code':''},'coverage':'single_image'}
  with patch.object(m,'LLM_KEY',''):
   d=m.app.test_client().post('/api/chat',json={'session_id':'unknown-media','message':'请帮我看这个指示灯','image':'uploaded:unknown.png'}).json
  self.assertIn('绿色灯亮',d['reply'])
  self.assertIn('具体产品型号',d['reply'])
  self.assertIn('待核验',d['reply'])
  self.assertFalse(any(c['kind']=='knowledge' for c in d['citations']))

 def test_video_missing_decoder(self):
  with patch('shutil.which',return_value=None):self.assertEqual(media.understand('a.mp4','url','key','model')['status'],'VIDEO_DECODER_MISSING')

 def test_video_sampling_uses_multiple_images(self):
  if not shutil.which('ffmpeg'):self.skipTest('ffmpeg not installed')
  with tempfile.TemporaryDirectory() as tmp:
   video=Path(tmp)/'sample.mp4'
   subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:d=6','-c:v','libx264',str(video)],check=True,capture_output=True)
   reply={'description':'A blue test frame','visible_issue':''}
   response=io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(reply)}}]}).encode())
   with patch('urllib.request.urlopen',return_value=response) as call:
    result=media.understand(video,'https://example.invalid/v1','test','test')
   self.assertEqual(result['status'],'OK');self.assertEqual(result['media_type'],'video')
   self.assertGreaterEqual(result['frame_count'],1);self.assertLessEqual(result['frame_count'],6)
   self.assertEqual(len(json.loads(call.call_args.args[0].data)['messages'][1]['content'])-1,result['frame_count'])
   self.assertEqual(result['sample_timestamps_seconds'],[i*5 for i in range(result['frame_count'])])
   self.assertEqual(result['audio_status'],'NOT_ANALYZED')

 def test_learning_pack_preserves_drafts(self):
  import long_tail_knowledge as lt
  entries=[e for e in lt.ENTRIES.values() if e['id'].startswith('long-tail-MM-LT-')]
  self.assertEqual(len(entries),40)
  self.assertTrue(all(e['review_status']=='draft_requires_review' for e in entries))
  self.assertIn('long-tail-MM-LT-016',[e['id'] for e in lt.retrieve('ASR没识别出文字')])
  self.assertIn('语言',lt.ENTRIES['long-tail-MM-LT-016']['strategy'])

 def test_evidence_has_hash_unknowns_and_unverified_status(self):
  response=io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps({'description':'Blurry label','unknowns':['model unclear']})}}]}).encode())
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a.png';p.write_bytes(b'image')
   with patch('urllib.request.urlopen',return_value=response) as call:
    result=media.understand(p,'https://example.invalid','key','qwen-max')
   body=json.loads(call.call_args.args[0].data)
   self.assertNotIn('thinking',body)
   self.assertIn('Audio is NOT analyzed',body['messages'][0]['content'])
   self.assertEqual(result['evidence']['verification_status'],'UNVERIFIED')
   self.assertEqual(result['audio_status'],'NOT_ANALYZED')
   self.assertEqual(len(result['sha256']),64)
   self.assertEqual(result['evidence']['unknowns'],['model unclear'])

 def test_old_case_media_rejected_after_reset(self):
  m.SESSIONS['reset-media']={'media_generation':'new'}
  m.VISION_CACHE['late.png']={'session_id':'reset-media','case_generation':'old','status':'OK','evidence':{'description':'old'}}
  result=m.app.test_client().post('/api/chat',json={'session_id':'reset-media','message':'看图','image':'uploaded:late.png'})
  self.assertEqual(result.status_code,400)
