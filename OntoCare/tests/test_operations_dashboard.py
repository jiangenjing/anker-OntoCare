"""Verify operational proposal provenance and the denominators used by the dashboard."""
import json,subprocess,unittest
from pathlib import Path
from test_attribution_workbench import build,analyze
ROOT=Path(__file__).resolve().parents[1]
class OperationsDashboardTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.report=analyze(build.snapshot())
  script="let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>console.log(JSON.stringify(require('./scripts/merchant_attribution/insights.js').proposals(JSON.parse(s)))));"
  cls.advice=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(cls.report).encode(),cwd=ROOT))
 def test_six_directions_have_valid_lineage_and_no_causal_percentage(self):
  self.assertEqual(len(self.advice),6)
  for a in self.advice:
   self.assertTrue(set(a['source_rows'])<=set(range(2,65)))
   self.assertIn(a['rule_id'],self.report['rules'])
   self.assertIsNone(a['contribution'])
   self.assertTrue(a['human_review_required'])
   self.assertEqual(len(a['trace']),4)
 def test_false_user_counts_not_imported(self):
  a={x['id']:x for x in self.advice}
  self.assertEqual(a['product']['source_rows'],[19,28])
  self.assertEqual(a['emotion']['source_rows'],[57,59,61])
  self.assertEqual(a['warranty']['source_rows'],[30,39,54,56])
  self.assertEqual(a['knowledge']['source_rows'],[14])
 def test_product_chart_denominator_and_reconciliation(self):
  from collections import Counter
  rows=self.report['tickets'];fault=[r for r in rows if r['scenario']=='Troubleshooting/Product usage'];counts=Counter(r['product'] for r in fault)
  self.assertEqual(len(fault),52)
  self.assertEqual(counts['X10 Pro'],11)
  self.assertEqual(counts['S1 Pro'],12)
  self.assertEqual(sum(counts.values()),52)
  self.assertEqual(sum('3212' in r['codes'] for r in rows),2)
 def test_empty_population_has_no_fabricated_rows(self):
  r=analyze({**build.snapshot(),'tickets':[]})
  self.assertEqual(r['executive_summary']['total_tickets'],0)
  self.assertEqual(r['statistics']['codes'],[])
if __name__=='__main__':unittest.main()
