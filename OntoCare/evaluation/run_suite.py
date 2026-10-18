"""Independent golden checks. Does not alter application code or send email."""
import json,sys,time,uuid,argparse,urllib.request,urllib.error,hashlib
from pathlib import Path
from datetime import date
from unittest.mock import patch
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT.parent))
import app as m
p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--ids',default='');args=p.parse_args()
suite=json.loads((ROOT/'ontocare-test-suite.json').read_text());results=[]
assert hashlib.sha256((ROOT/'source-snapshot.json').read_bytes()).hexdigest()==suite['metadata']['source_snapshot_sha256'], 'Source snapshot version mismatch'
if not args.live:m.LLM_KEY=''
client=m.app.test_client()
def request(path,body=None):
 start=time.monotonic()
 if args.live:
  req=urllib.request.Request('http://127.0.0.1:5088'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=110) as r:status=r.status;data=r.read().decode()
  except urllib.error.HTTPError as e:status=e.code;data=e.read().decode()
 else:
  r=client.post(path,json=body) if body is not None else client.get(path);status=r.status_code;data=r.get_data(as_text=True);r.close()
 try:out=json.loads(data)
 except json.JSONDecodeError:
  events=[json.loads(x) for x in data.splitlines() if x.strip()];out=next((e['data'] for e in reversed(events) if e.get('type')=='result'),{'error':events[-1] if events else 'empty stream'})
 return status,out,round(time.monotonic()-start,3)
def assertion(label,ok,actual=None):return {'check':label,'passed':bool(ok),'actual':actual}
def verify(case,status,d):
 out=[];trace=d.get('trace',{});reply=d.get('reply','');citations=[c['id'] for c in d.get('citations',[])]
 for a in case['automated_checks']:
  kind=a['type'];ok=False;actual=None
  if kind.startswith('trace'):
   actual=trace.get(a['path'])
   if kind=='trace':ok=actual==a['equals']
   elif kind=='trace_one_of':ok=actual in a['values']
   else:ok=a['value'].lower() in str(actual).lower()
  elif kind=='citation_any':actual=citations;ok=bool(set(a['ids'])&set(actual))
  elif kind=='blocked':actual=trace.get('forbidden',[]);ok=set(a['values'])<=set(actual)
  elif kind.startswith('reply_contains'):
   actual=reply;hits=[v.lower() in reply.lower() for v in a['values']];ok=all(hits) if kind=='reply_contains' else any(hits)
  elif kind=='http':actual=status;ok=status==a['status']
  elif kind=='order_fields':
   card=d.get('order_snapshot') or {};actual=card;ok=card.get('order_id','').upper()==a['order_no'].upper()
   for row in a['rows']:
    item=next((i for i in card.get('items',[]) if i['source_row']==row['source_row']),{})
    ok=ok and all(item.get('fields',{}).get(k)==v for k,v in row['fields'].items())
  out.append(assertion(json.dumps(a,ensure_ascii=False),ok,actual))
 out.append(assertion('HTTP成功',status==200,status))
 return out
selected=set(args.ids.split(',')) if args.ids else None
analytics=None
for case in suite['user_test_cases']+suite['merchant_test_cases']:
 if selected and case['id'] not in selected:continue
 start=time.monotonic();checks=[];status='REVIEW_REQUIRED';response=None;trajectory=[]
 try:
  asof=case.get('as_of_date','2026-10-16')
  if args.live and asof!='2026-10-16':
   results.append({'id':case['id'],'status':'BLOCKED','reason':'live接口不支持as_of_date注入','checks':[]});continue
  class Clock(date):
   @classmethod
   def today(cls):return date.fromisoformat(asof)
  with patch.object(m,'date',Clock):
   if case['id'].startswith('U'):
    sid='eval-'+uuid.uuid4().hex
    turns=case.get('setup_turns',[])+case.get('turns',[case['input']])
    for text in turns:
     http,response,elapsed=request('/api/chat',{'message':text,'session_id':sid,'language':case['language']})
     trajectory.append({'input':text,'response':response,'seconds':elapsed,'http_status':http})
    checks=verify(case,http,response)
   else:
    kind=case['evaluation_kind'];row=case.get('input_ticket_row')
    if analytics is None:_,analytics,_=request('/api/analytics')
    rec=next((r for r in analytics['records'] if r['row']==row),{})
    if kind=='emotion':
     score=rec.get('emotion',{}).get('score');band='high' if score is not None and score>=7 else 'medium' if score is not None and score>=4 else 'low'
     checks=[assertion('独立情绪强度标签',band==case['gold_band'],{'score':score,'band':band})];response=rec
    elif kind=='root':
     signals=rec.get('signals',[]);checks=[assertion('无证据不输出已证实根因',not any(s['rule_id'] in case['expected_unproven_tags'] and '待核查' not in s.get('status','') for s in signals),signals)];response=rec
    elif kind in ('aggregation','drilldown'):
     chart=next((c for c in analytics['charts'] if c['key']==case['dimension']),None);response=chart
     if not chart:checks=[assertion('所需统计维度存在',False,list(c['key'] for c in analytics['charts']))]
     elif kind=='drilldown':
      bucket=next((b for b in chart['buckets'] if b['label']==case['selected_label']),{});checks=[assertion('下钻接口行号集合',set(bucket.get('rows',[]))==set(case['expected_ticket_rows']),bucket.get('rows'))]
     else:
      expected=case['expected_aggregation'];actual={b['label']:b for b in chart['buckets']}
      checks=[assertion('分类集合',set(actual)=={b['label'] for b in expected['buckets']},list(actual))]
      for b in expected['buckets']:
       got=actual.get(b['label'],{});ok=got.get('count')==b['count'] and set(got.get('rows',[]))==set(b['rows']) and abs(got.get('share',-1000)-b['share'])<1e-6 and abs(got.get('cumulative',-1000)-b['cumulative'])<1e-6
       checks.append(assertion(b['label'],ok,got))
    elif kind=='recommendation':
     response=rec;got=rec.get('knowledge_ids',[]);gold=case['expected_knowledge_ids']
     checks=[assertion('同PN且相关知识ID或明确知识缺口',bool(set(gold)&set(got)) if gold else not got,got)]
     checks.append(assertion('TOP错误码被正确提取',case['target_code'] in rec.get('codes',[]),rec.get('codes')))
    elif kind=='eligibility':
     http,response,elapsed=request('/api/mail/stream',{'message':case['input_email'],'ticket_row':row,'language':'en'})
     trace=response.get('trace',{});checks=[assertion('质保状态',trace.get('warranty')==case['expected_case_state']['warranty'],trace.get('warranty')),assertion('禁止越权',set(case['expected_blocked_actions'])<=set(trace.get('forbidden',[])),trace.get('forbidden')),assertion('仅草稿未发信',response.get('status')=='DRAFT_ONLY' and response.get('ontology',{}).get('Action',{}).get('email_sent') is False,response.get('ontology'))]
    elif kind=='weekly':
     _,response,_=request('/api/analytics/report/weekly');blocks=response.get('blocks',[]);checks=[assertion('周报包含产品线而非产品名',any('产品线' in b.get('title','') and 'data' in b for b in blocks),[b['title'] for b in blocks]),assertion('声明是快照', '快照' in response.get('scope',''),response.get('scope'))]
     codeblock=next((b for b in blocks if 'TOP 错误码' in b['title']),{});checks.append(assertion('TOP3错误码',[(x['label'],x['count']) for x in codeblock.get('data',[])][:3]==[(x['label'],x['count']) for x in case['expected_top_codes']],codeblock.get('data')))
    elif kind=='oversized':
     http,response,_=request('/api/mail/stream',{'message':case['input_email']*case['input_transform']['times'],'language':'en'});checks=[assertion('超长邮件明确拒绝',http==400,http)]
    elif kind=='tone':
     if not args.live:
      status='BLOCKED';response={'reason':'离线模式不调用模型；语气改写需运行真实模型测评。'}
     else:
      http,draft,_=request('/api/mail/stream',{'message':case['input_email'],'ticket_row':row,'language':'en'})
      original=draft.get('draft','')
      tone='formal' if case['id']=='M018' else 'empathetic'
      http,response,_=request('/api/mail/rewrite',{'text':original,'action':'tone','language':'en','tone':tone})
      import mail_editing
      checks=[assertion('真实语气接口成功',http==200,http),assertion('完整正文被改写',bool(response.get('text')) and response.get('text')!=original,response),assertion('业务字段与引用数量不变',mail_editing.protected(response.get('text',''))==mail_editing.protected(original))]
      response={'original':original,'tone':tone,'result':response,'draft_citations':draft.get('citations',[])}
   if any(not c['passed'] for c in checks):status='FAIL'
   elif case.get('evaluation_kind')=='oversized':status='PASS'
  results.append({'id':case['id'],'category':case['category'],'status':status,'hard_checks_passed':bool(checks) and all(c['passed'] for c in checks),'checks':checks,'response':response,'trajectory':trajectory,'seconds':round(time.monotonic()-start,3),'semantic_review':'NOT_REVIEWED'})
 except Exception as exc:results.append({'id':case['id'],'status':'ERROR','reason':str(exc),'checks':[]})
 print(case['id'],results[-1]['status'],flush=True)
output={'mode':'LIVE_HTTP_CONFIGURED_MODEL' if args.live else 'OFFLINE_RULES_LLM_DISABLED','scope':'硬断言回归，不等价完整语义或UI验收','reference_date':'2026-10-16','counts':{s:sum(r['status']==s for r in results) for s in ['PASS','FAIL','REVIEW_REQUIRED','BLOCKED','ERROR']},'results':results}
(ROOT/('results-live.json' if args.live else 'results-offline.json')).write_text(json.dumps(output,ensure_ascii=False,indent=2))
print(output['counts'])
