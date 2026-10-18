"""Replacement dependency probe: U060 now bypasses the model by design.
Keep the original U060 result; test timeout on an uncached knowledge request separately.
"""
import copy,importlib.util,json
from pathlib import Path
D=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('runner',D/'ontocare-benchmark-runner.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def main():
 case=copy.deepcopy(next(c for c in r.cases() if c['id']=='U060'))
 case.update(id='U060-R1',fault_injection='timeout')
 case['turns']=[{'turn':1,'input':'T8D04自定义吸乳节奏如何设置？','trigger':'always'}]
 # Keep the original HTTP, citation, read-only and failure-disclosure assertions.
 result=r.run_trial((case,'offline',1,False))
 payload={'reason':'Original U060 uses a fixed EB1L workflow and no longer invokes the model. This separate uncached request must actually hit the injected timeout. Not a replacement for historical results.','case':case,'result':result}
 (D/'repair-fault-probe.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
 print(json.dumps({'id':result['id'],'status':result['status'],'fault_hits':result['extras']['fault_hits'],'failures':[c for c in result['checks'] if not c['passed']]},ensure_ascii=False))
if __name__=='__main__':main()
