import json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DecisionChatTests(unittest.TestCase):
 def test_four_versions_preserve_evidence_and_all_six_recommendations(self):
  script="""const fs=require('fs'),vm=require('vm');const REPORT=JSON.parse(fs.readFileSync('reports/attribution_report.json'));const s=fs.readFileSync('scripts/merchant_attribution/dashboard.js','utf8');let ctx={advice:REPORT.improvement_advice,all:REPORT.tickets};vm.createContext(ctx);vm.runInContext(s.slice(s.indexOf('const decisionQuestion='),s.indexOf('function addDecisionMessage')),ctx);console.log(JSON.stringify([0,1,2,3].map(n=>vm.runInContext('standardDecision('+n+')',ctx))));"""
  answers=json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT))
  self.assertEqual(len(set(answers)),4)
  report=json.loads((ROOT/'reports/attribution_report.json').read_text())
  for answer in answers:
   self.assertIn('63 条工单',answer)
   self.assertIn('不计算产品故障率',answer)
   for a in report['improvement_advice']:
    self.assertIn(a['problem'],answer)
    self.assertIn(a['rule_id'],answer)
    for row in a['source_rows']:self.assertIn(f'工单第{row}行',answer)
 def test_html_has_two_tabs_and_honest_modes(self):
  html=(ROOT/'static/analytics.html').read_text()
  self.assertNotIn('data-tab="summary"',html)
  self.assertEqual(html.count('role="tab"'),2)
  self.assertIn('未调用模型',html)
  self.assertIn("fetch('/api/analytics/chat'",html)
  self.assertNotIn('Bearer ',html)
