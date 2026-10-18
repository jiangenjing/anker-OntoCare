import unittest
from unittest.mock import patch
import tempfile,json
from pathlib import Path
import app as m
import attribution as a
import analytics_api
import mail_editing
class AttributionTests(unittest.TestCase):
 def test_real_rows_and_no_fake_customer(self):
  rows=a.records();self.assertEqual(len(rows),63)
  self.assertTrue(all(r['profile']['customer_id']=='未提供' for r in rows))
  for r in rows:
   with m.app.test_client() as c:self.assertEqual(c.get(r['citation']['url']).status_code,200)
 def test_error_codes_not_years_sku_tracking(self):
  self.assertEqual(a.extract_error_codes('2026-10-16 T2351 Anker1234567 $1099'),[])
  self.assertEqual(a.extract_error_codes('Error code: 6011; EB1L'),['6011','EB1L'])
 def test_no_forced_root_cause(self):
  with patch.object(a,'TICKETS',[{'原文行号':2,'客户首封邮件内容':'Hello','SKU':''}]):
   self.assertEqual(a.records()[0]['signals'],[])
 def test_pareto_counts_and_drilldown(self):
  d=a.dashboard()
  for c in d['charts']:
   self.assertEqual(sum(b['count'] for b in c['buckets']),c['total'])
   self.assertAlmostEqual(c['buckets'][-1]['cumulative'],100)
   self.assertTrue(all(b['count']==len(b['rows']) for b in c['buckets']))
   self.assertIn(c['recommendation']['rule_id'],['AN-SCENARIO','AN-PRODUCT','AN-CODE','AN-REGION'])
 def test_multi_code_denominator(self):
  c=a.pareto([{'row':1,'codes':['6011','6012']},{'row':2,'codes':[]}],'codes')
  self.assertEqual(c['total'],3)
 def test_unknown_country_and_conflict(self):
  self.assertEqual(a.country('Ontario'),'未提供');self.assertEqual(a.country('United States'),'US')
  self.assertEqual(a.country('United States Germany'),'未提供')
 def test_reports_missing_data(self):
  self.assertEqual(len(a.report('weekly')['blocks']),7)
  for kind in ['daily','weekly','monthly','quarterly']:
   d=a.report(kind);self.assertFalse(d['sent']);self.assertEqual(d['status'],'PREVIEW_ONLY')
  self.assertIn('不是售后成本',a.report('quarterly')['blocks'][0]['text'])
 def test_api_and_gap_review_no_publication(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(analytics_api,'REVIEWS',Path(tmp)/'review.json'):
   with m.app.test_client() as c:
    response=c.get('/analytics');self.assertEqual(response.status_code,200);response.close()
    self.assertEqual(c.get('/api/analytics').status_code,200)
    self.assertEqual(c.get('/api/analytics/report/bad').status_code,400)
    rows=c.get('/api/analytics/gaps').json['rows']
    if rows:
     out=c.post('/api/analytics/gaps',json={'id':rows[0]['id'],'status':'approved'})
     self.assertEqual(out.status_code,200)
     self.assertEqual(out.json['rows'][0]['status'],'approved')
    self.assertEqual(c.post('/api/analytics/gaps',json={'id':'bad','status':'approved'}).status_code,400)
 def test_rewrite_protects_fields(self):
  text='Order Anker002 SKU T2080GA1 costs 1099.99 [1]'
  with self.assertRaises(ValueError):mail_editing.rewrite(lambda *a,**kw:json.dumps({'text':'Order Anker003 costs 20'}),text,'translate')
  self.assertEqual(mail_editing.rewrite(lambda *a,**kw:json.dumps({'text':text}),text,'translate')['text'],text)
 def test_all_versions_validated(self):
  text='T2080 Anker002 [1]'
  with self.assertRaises(ValueError):mail_editing.rewrite(lambda *a,**kw:json.dumps({'short':text,'standard':text,'detailed':text+' 24'}),text,'versions')

 def test_frontend_scripts_are_served(self):
  with m.app.test_client() as c:
   for path in ['/analytics.js','/merchant_assist.js','/merchant_extra.js']:
    response=c.get(path);self.assertEqual(response.status_code,200);response.close()

 def test_tracking_is_not_a_sku(self):
  self.assertEqual(mail_editing.protected('live tracking'),[])
  self.assertEqual(mail_editing.protected('Live-Tracking'),[])
