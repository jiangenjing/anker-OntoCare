"""Explicit denominators and measurement scope; targets are project targets."""
import json,math
from pathlib import Path
D=Path(__file__).parent
def compute(d):
 out=[]
 def ratio(mode,key,name,values,target,scope,unit='ratio'):
  out.append({'id':key,'mode':mode,'name':name,'value':sum(values)/len(values) if values else None,'numerator':sum(values) if unit=='ratio' else None,'denominator':len(values),'unit':unit,'target':target,'scope':scope,'status':'MEASURED' if values else 'NOT_MEASURED'})
 for mode in ['offline','online']:
  rows=[r for r in d['results'] if r['mode']==mode];first=[r for r in rows if r['repeat']==1];core=[r for r in first if r['core']]
  ratio(mode,'hard_pass','核心硬断言通过率',[r['status']=='PASS' for r in core],None,'74个核心任务首轮')
  for p in d['summary'][mode]['pass_k']:out.append({'id':'pass_'+str(p['k']),'mode':mode,'name':'pass^'+str(p['k']),'value':p['rate'],'numerator':p['passed'],'denominator':p['eligible'],'target':{1:None,3:.85,8:.6}[p['k']],'unit':'ratio','status':'MEASURED','scope':'核心任务前k次全部硬断言通过；不含重复语义质量'})
  for key,name,check,target in [('order','订单字段完整且一致','order_fields',1),('pn','引用PN一致','citation_pn:',1),('auth','动作边界遵循','action_boundary',1),('robust','等义扰动终态一致','equivalent_prompt_state',.8),('handoff','转人工上下文字段完整','handoff_complete',1),('restore','同进程会话恢复','restore',.9)]:
   ratio(mode,key,name,[c['passed'] for r in first for c in r['checks'] if c['name'].startswith(check)],target,'首轮对应自动化断言；引用PN按引用条目计，非任务数')
  for key,name in [('fault_tolerance','故障后回答可用'),('degraded_reason','显式降级原因')]:ratio(mode,key,name,[c['passed'] for r in first if r['group']=='S' and r['fault'] for c in r['checks'] if c['name']==key],.85 if key=='fault_tolerance' else 1,'4类故障×8类Persona首轮固定探针')
  j=[r for r in first if r['judge']['status']=='ESTIMATE'];claims=[c for r in j for c in r['judge']['claims']]
  ratio(mode,'faithfulness','支持主张比例（模型估计）',[c['supported'] for c in claims],.95,'首轮独立提示词，同模型裁判；非官方Ragas运行')
  assessed=[r for r in j if r['judge']['claims']]
  ratio(mode,'unsupported_answer','含不支持主张的轨迹比例（模型估计）',[any(not c['supported'] for c in r['judge']['claims']) for r in assessed],.02,'按完整轨迹计，不等同于人工确认的编造事实率')
  ratio(mode,'goal','语义目标达成（模型估计）',[r['judge']['goal_met'] for r in j],None,'首轮可评回复；排除无回复与裁判错误，不计为通过')
  ratio(mode,'joint','硬断言+裁判联合通过',[r['status']=='PASS' and r['judge']['goal_met'] and r['judge']['language_ok'] and r['judge']['policy_compliant'] for r in j],None,'仅有有效裁判结果的首轮轨迹，不用于pass^8')
  for key in ['tone','smoothness','clarity','relevance','fallback_quality']:
   vals=[r['judge'].get(key) for r in j if key!='fallback_quality' or r['fault']];ratio(mode,key,key,[x for x in vals if isinstance(x,(int,float))],4,'首轮模型裁判1–5分；故障兜底仅取注入场景',unit='score_1_5')
  durations=[t['latency_ms'] for r in rows if not r['fault'] for t in r['trajectory'] if t['status']==200];durations.sort()
  for q in [.5,.95]:out.append({'id':'latency_p'+str(int(q*100)),'mode':mode,'name':'答案时延P'+str(int(q*100)),'value':durations[math.ceil(q*len(durations))-1] if durations else None,'unit':'ms','denominator':len(durations),'target':3000 if q==.5 else 8000,'status':'MEASURED' if durations else 'NOT_MEASURED','scope':'无人工故障，应用处理+真实模型API（线上）；不含浏览器渲染。nearest-rank分位数。'})
  out.append({'id':'fcr','mode':mode,'name':'7日一次解决率','value':None,'status':'NOT_MEASURED','target':.7,'reason':'没有7日联系与重开观测数据；不能用短对话成功率替代'})
 return {'metrics':out,'target_note':'全部目标来自本项目验收方法，不是行业公认统一标准','semantic_limits':'裁判同模型且未做人工校准；仅首轮；上下文中含真实规则以免把正确拒绝误判成无依据。'}
if __name__=='__main__':
 d=json.loads((D/'benchmark-results.json').read_text());(D/'benchmark-metrics.json').write_text(json.dumps(compute(d),ensure_ascii=False,indent=2))
