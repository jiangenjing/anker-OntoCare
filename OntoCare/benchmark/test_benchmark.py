import unittest,json,importlib.util,copy
from pathlib import Path
D=Path(__file__).parent
spec=importlib.util.spec_from_file_location('runner',D/'ontocare-benchmark-runner.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class BenchmarkIntegrity(unittest.TestCase):
 def test_complete_matrix_and_exact_personas(self):
  cases=r.cases();self.assertEqual(len(cases),110);self.assertEqual(sum(c['core'] for c in cases),74)
  faults={(c['fault_injection'],c['persona_id']) for c in cases if c['group']=='S' and c['fault_injection']}
  self.assertEqual(len(faults),32)
  source=json.loads((D.parent/'evaluation/source-snapshot.json').read_text())
  for p in json.loads((D/'ontocare-persona-vectors.json').read_text())['personas']:
   row=next(x for x in source['客诉工单信息'] if x['row']==p['source_excel_row']);self.assertEqual(p['first_message'],row['values'][2])
  for c in cases:
   for ref in c['ground_truth_refs']:
    row=next(x for x in source[ref['sheet']] if x['row']==ref['excel_row']);self.assertEqual(ref['values'],row['values'][:14])
 def test_passk_requires_every_trial_and_excludes_incomplete(self):
  rows=[{'id':'A','core':True,'repeat':i,'status':'PASS' if i!=2 else 'FAIL'} for i in range(1,9)]
  rows += [{'id':'B','core':True,'repeat':1,'status':'PASS'}]
  self.assertEqual(r.pass_k(rows,1)['rate'],1)
  self.assertEqual(r.pass_k(rows,3),{'k':3,'passed':0,'eligible':1,'rate':0})
  self.assertEqual(r.pass_k(rows,8)['eligible'],1)
  self.assertIsNone(r.pass_k([],8)['rate'])
 def test_wrong_order_field_is_detected_and_empty_stays_empty(self):
  c=next(c for c in r.cases() if c['id']=='U001');v=c['ground_truth_refs'][0]['values'];fields=['No.','订单号','SKU','Product Description','QTY','购买日期','质保结束日期','订单地址','订单状态','物流承运商','物流单号','物流状态','发货日期','订单金额']
  d={'reply':'source record','citations':[{'id':'order-2'}],'order_snapshot':{'order_id':'Anker001','items':[{'source_row':2,'fields':{k:r.normalized(v[i]) for i,k in enumerate(fields) if i!=1}}]}}
  item=d['order_snapshot']['items'][0];address=item['fields']['订单地址'];item['fields']['订单地址']='未核验，已隐藏';item['redacted_fields']=['订单地址'];d['order_snapshot']['ownership_verified']=False
  trajectory=[{'status':200,'response':d}];extras={'order_unchanged':True,'resolvable_ids':['order-2']}
  get=lambda:next(a['passed'] for a in r.check_case(c,trajectory,{},extras) if a['name']=='order_fields')
  self.assertTrue(get());item['fields']['订单地址']=address;self.assertFalse(get());item['fields']['订单地址']='未核验，已隐藏';d['order_snapshot']['items'][0]['fields']['SKU']='WRONG';self.assertFalse(get())
 def test_fault_must_actually_hit_and_disclose_reason(self):
  c=next(c for c in r.cases() if c['id']=='U051');t=[{'status':200,'response':{'reply':'I cannot check right now.','citations':[{'id':'service-rules'}]}}]
  checks=r.check_case(c,t,{}, {'order_unchanged':True,'fault_hits':0,'resolvable_ids':['service-rules']})
  self.assertFalse(next(x['passed'] for x in checks if x['name']=='fault_tolerance'))
  self.assertFalse(next(x['passed'] for x in checks if x['name']=='degraded_reason'))
 def test_restore_order_case_is_not_a_product_failure(self):
  c=next(c for c in r.cases() if c['id']=='U063');t=[{'status':200,'response':{'reply':'x'}},{'status':200,'response':{'reply':'y'}}]
  extra={'order_unchanged':True,'restore':{'turn_count':2,'transcript':[{}, {}, {}, {}],'order_snapshot':{'order_id':'Anker002'}}}
  self.assertTrue(next(x['passed'] for x in r.check_case(c,t,{},extra) if x['name']=='restore'))
if __name__=='__main__':unittest.main()
