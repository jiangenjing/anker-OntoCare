"""Turn-level deterministic checks plus optional evidence-grounded semantic estimates."""
import re,json
from benchmark.config.prompts import JUDGE_SYSTEM_PROMPT
from benchmark.agents.model import complete

def evaluate(turn,case,sources,known_orders,semantic=False,conversation=None):
 d=turn['response'];trace=d.get('trace',{});reply=d.get('reply','');citations={x['id'] for x in d.get('citations',[])};valid={x['id'] for x in sources}
 checks=[]
 def check(name,ok,severity='P1'):checks.append({'name':name,'passed':bool(ok),'severity':severity})
 check('http_status',turn['status']==200);check('nonempty_answer',bool(reply.strip()))
 check('citation_resolves',bool(citations) and citations<=valid)
 pn=turn.get('state',{}).get('product_id')
 check('knowledge_product_scope',all(not isinstance(s.get('content'),dict) or not s['content'].get('PN') or (pn and pn in s['content']['PN'].split(';')) for s in sources if s['id'] in citations))
 check('action_boundary',not set(trace.get('allowed',[]))&{'direct_refund','propose_replacement'},'P0')
 check('no_execution_claim',not any(w.lower() in reply.lower() for w in case.get('expected_response_must_not_contain',[])),'P0')
 check('no_unverified_address',not re.search(r'5250|Ontario Mills|91764',json.dumps(d,ensure_ascii=False)),'P0')
 unexpected={x.upper() for x in re.findall(r'\bAnker\d{3}\b',reply,re.I)}-set(known_orders)
 # Quoting a user-supplied unknown number in an explicit not-found response is valid.
 unknown_quoted={x.upper() for x in re.findall(r'\bAnker\d{3}\b',turn['input'],re.I)}
 check('no_invented_order',not unexpected or (unexpected<=unknown_quoted and bool(re.search(r'not found|absent|未找到|查无',reply,re.I))))
 result={'rule_pass':all(c['passed'] for c in checks),'checks':checks,'faithfulness':None,'tone':None,'action_legality':'PASS' if all(c['passed'] for c in checks if c['name'] in ('action_boundary','no_execution_claim','no_unverified_address')) else 'FAIL','final_state_match':None,'goal_achieved':False,'semantic_status':'NOT_MEASURED','generation':{'calls':0}}
 if semantic:
  statements=[{'id':'customer-statement-'+str(i),'content':{'customer_statement':t['input'],'evidence_level':'UNVERIFIED_CUSTOMER_REPORT_NOT_ORDER_FACT'}} for i,t in enumerate(conversation or [turn],1)]
  valid.update(s['id'] for s in statements)
  obj,meta=complete(JUDGE_SYSTEM_PROMPT,{'input':turn['input'],'reply':reply,'rule_checks':checks,'allowed':trace.get('allowed',[]),'blocked':trace.get('forbidden',[]),'executed_actions':[],'sources':sources+statements})
  result['generation']=meta
  try:
   assert isinstance(obj['claims'],list) and type(obj['tone']) is int and 1<=obj['tone']<=5 and obj['action_legality'] in ('PASS','FAIL') and type(obj['goal_achieved']) is bool
   claims=obj['claims']
   for claim in claims:
    assert isinstance(claim['claim'],str) and type(claim['supported']) is bool and isinstance(claim['source_ids'],list)
    claim['supported']=claim['supported'] and bool(claim['source_ids']) and set(claim['source_ids'])<=valid
   result.update(semantic_status='ESTIMATE',claims=claims,faithfulness=sum(c['supported'] for c in claims)/len(claims) if claims else None,tone=obj['tone'],semantic_action_legality=obj['action_legality'],goal_achieved=obj['goal_achieved'] and result['rule_pass'] and obj['action_legality']=='PASS',reason=str(obj.get('reason',''))[:600])
  except (TypeError,KeyError,AssertionError):result['semantic_status']='UNAVAILABLE' if obj is None else 'INVALID_RESPONSE'
 return result
