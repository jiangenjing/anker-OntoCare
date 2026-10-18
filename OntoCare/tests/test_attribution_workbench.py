import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('merchant_build',ROOT/'scripts/merchant_attribution/build.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
def analyze(snapshot):
    script="const a=require('./static/merchant-attribution-agent.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(a.analyzeComplaints(JSON.parse(s)))));"
    return json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(snapshot).encode(),cwd=ROOT))
class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=build.snapshot();cls.data=analyze(cls.snapshot)
    def test_population_and_partition(self):
        self.assertEqual(len(self.data['tickets']),63)
        rows=[n for b in self.data['statistics']['scenario'] for n in b['source_rows']]
        self.assertEqual(sorted(rows),list(range(2,65)))
        self.assertEqual([b['count'] for b in self.data['statistics']['scenario']],[52,11])
        self.assertEqual(len(self.snapshot['knowledge']),875)
        self.assertEqual(len(self.snapshot['orders']),16)
    def test_product_and_original_mail(self):
        from dataset import load_dataset
        originals={r['原文行号']:r for r in load_dataset()[4]}
        for t in self.data['tickets']:
            self.assertEqual(t['email'],originals[t['row']]['客户首封邮件内容'])
            self.assertEqual(t['product'],originals[t['row']]['产品名'])
        self.assertEqual([b['count'] for b in self.data['statistics']['product'][:3]],[14,13,12])
    def test_repeated_code_is_not_x10_design_defect(self):
        code=next(x for x in self.data['statistics']['codes'] if x['label']=='3212')
        self.assertEqual(code['source_rows'],[19,28])
        a=self.data['attributions'][0]
        self.assertEqual(a['confidence'],'low');self.assertEqual(a['evidence_rows'],[19,28])
        self.assertEqual(self.data['rc_counts'],{'RC1':0,'RC2':0,'RC3':2,'RC4':0})
        self.assertEqual(self.data['actions'][0]['priority'],'P2')
    def test_same_code_without_symptom_match_is_not_cross_model_cause(self):
        import copy
        s=copy.deepcopy(self.snapshot)
        for t in s['tickets']:
            if t['row'] in (19,28):t['email']='Error 3212'
        self.assertEqual(analyze(s)['rc_counts']['RC3'],0)
    def test_rc4_boundary_uses_complaint_date_not_today(self):
        import copy
        s=copy.deepcopy(self.snapshot)
        for t in s['tickets']:t['complaint_date']=None;t['warranty_end']=None
        for t,date in zip(s['tickets'],['2026-10-02','2026-10-31','2026-11-01']):
            t['complaint_date']=date;t['warranty_end']='2026-10-01'
        r=analyze(s)
        self.assertEqual(r['warranty_window']['confirmed_candidates'],2)
        self.assertEqual(r['warranty_window']['assessable_tickets'],3)
        self.assertEqual(r['warranty_window']['source_rows'],[2,3])
    def test_action_and_knowledge_trace(self):
        for a in self.data['actions']:
            self.assertIn(a['rule_id'],self.data['rules'])
            self.assertTrue(set(a['source_rows'])<=set(range(2,65)))
            self.assertTrue(a['source_trace'])
        kb={k['id']:k for k in self.snapshot['knowledge']}
        for c in self.data['knowledge_coverage']:
            for k in c['knowledge_ids']:
                self.assertIn(c['pn'],kb[k]['pn']);self.assertTrue(kb[k]['visible'])
    def test_dashboard_remains_embedded_and_has_no_export_dependency(self):
        html=(ROOT/'static/analytics.html').read_text()
        for token in ['__REPORT__','<script src=','生成改进报告','createObjectURL','window.print']:
            self.assertNotIn(token,html)
        self.assertNotIn('高管摘要',html);self.assertIn('归因与决策',html);self.assertIn('data:image/png;base64,',html)
