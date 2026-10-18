"""Read-only, evidence-bound merchant conversation over the workbench snapshot."""
import json
import re
from pathlib import Path
from collections import Counter
from action_gateway import public_data

ROOT=Path(__file__).parent
PROMPT=ROOT/'docs/prompts/agents/analytics/Agent.md'


def read_ontology(report, query, context):
    """ReadOntology: select actual product entities and defined decision rules."""
    products=sorted({t['product'] for t in report['tickets']},key=len,reverse=True)
    product=next((p for p in products if p.lower() in query.lower()),None)
    tag=re.search(r'\bRC[1-4]\b',query,re.I)
    rule='DO-'+tag.group().upper() if tag else ('DO-RC4' if '过保' in query else None)
    if not product and not rule and re.search(r'它|这些|这个|继续|具体|怎么|如何|建议',query):
        product=context.get('product') if context.get('product') in products else None
        rule=context.get('rule_id') if context.get('rule_id') in report['rules'] else None
    rule=rule or 'DO-OPS-FOCUS'
    return {'product':product,'rule_id':rule,'definition':report['rules'][rule]['definition']}


def read_trace(report, selection):
    """ReadTrace: retrieve recorded attribution audits, never fabricated model reasoning."""
    product=selection['product'];rule=selection['rule_id']
    tickets=[t for t in report['tickets'] if not product or t['product']==product]
    rows={t['row'] for t in tickets}
    audits=[a for a in report['attributions'] if (rule=='DO-OPS-FOCUS' or a['rule_id']==rule)
            and set(a['evidence_rows']) & rows]
    if rule.startswith('DO-RC'):
        ids={n for a in audits for n in a['evidence_rows']}
        tickets=[t for t in tickets if t['row'] in ids]
    actions=[a for a in report['actions'] if a['rule_id']==rule and
             (not product or set(a['source_rows']) & rows)]
    return {'tickets':tickets,'audits':audits,'actions':actions}


def answer(query, context, llm, report=None):
    report=report or json.loads((ROOT/'reports/attribution_report.json').read_text())
    selection=read_ontology(report,query,context)
    trace=read_trace(report,selection)
    tickets=trace['tickets'];rows=[t['row'] for t in tickets]
    total=len(report['tickets']);count=len(tickets)
    subject=selection['product'] or report['rules'][selection['rule_id']]['name']
    fact=f'按全量快照，{subject}关联 {count} 条工单，占全部 {total} 条工单的 {count/total*100:.1f}%。'
    if selection['rule_id']=='DO-RC4':
        w=report['warranty_window']
        fact+=f" 全量中 {w['assessable_tickets']} 条可核算过保窗口，{w['unassessed_tickets']} 条缺少完整关联条件。"
    scenarios=Counter(t['scenario'] for t in tickets)
    if scenarios:fact+=' 咨询场景：'+'；'.join(f'{k} {v} 条' for k,v in scenarios.most_common())+'。'
    codes=Counter(c for t in tickets for c in set(t.get('codes',[])))
    if codes:fact+=' 已记录错误码：'+'；'.join(f'{k}（{v} 条）' for k,v in codes.most_common(5))+'。'
    fact+=' 投诉日期覆盖不完整，无法判断“最近增加”；缺少销量分母，不能推断故障率或确认设计缺陷。'
    audit_text=' '.join(a['audit_summary']['fact']+' '+a['audit_summary']['conclusion'] for a in trace['audits'])
    recommendation='；'.join(a['action'] for a in trace['actions']) or ('先核查投诉日期、对应 SKU 和质保结束日期，再判断是否满足分析窗口。' if selection['rule_id']=='DO-RC4' else '抽查对应工单原文、已尝试步骤与同型号知识条目，补齐证据后再判断原因。')
    chain=[
        {'step':1,'type':'data','label':f'全量快照 → {count} 条匹配工单','definition':report['period'],'evidence_rows':rows},
        {'step':2,'type':'ontology','label':'Service Ontology → '+subject,'definition':'按源表产品实体、场景及错误码关联；不推断未记录的症状。','evidence_rows':rows},
        {'step':3,'type':'rule','label':'Decision Ontology → '+selection['rule_id'],'definition':selection['definition']+' '+(audit_text or '当前匹配范围未记录该归因候选。'),'evidence_rows':sorted({n for a in trace['audits'] for n in a['evidence_rows']})},
        {'step':4,'type':'suggestion','label':'建议行动（未执行）','definition':recommendation,'evidence_rows':rows}]
    evidence={str(t['row']):{k:t.get(k) for k in ['row','product','email','sku','order_no']} for t in tickets}
    # Pass only bounded evidence, never all order addresses or hidden customer records.
    payload={'question':query,'facts':fact,'selection':selection,'audit_summary':audit_text,
             'recommended_action':recommendation,'source_rows':rows,
             'mail_excerpts':[{**e,'email':e['email'][:1200]} for e in list(evidence.values())[:16]]}
    raw=llm(PROMPT.read_text(),json.dumps(public_data(payload),ensure_ascii=False))
    mode='规则摘要 · 模型暂不可用';advice=recommendation
    if raw:
        try:
            generated=json.loads(raw);text=generated['advice'];refs=generated['source_rows']
            if (isinstance(text,str) and 0<len(text)<=2400 and isinstance(refs,list)
                and all(type(n)==int and n in rows for n in refs)
                and (refs or not rows)):
                # Numerical claims must come from supplied facts, not the model.
                allowed=set(re.findall(r'\d+(?:\.\d+)?',fact+' '+audit_text+' '+recommendation))
                if set(re.findall(r'\d+(?:\.\d+)?',text))<=allowed:
                    advice=text;mode='LLM 分析建议 · 待核查'
        except (ValueError,KeyError,TypeError):pass
    return {'reply':'\n\n'.join(x for x in [fact,audit_text,'建议：'+advice] if x),'mode':mode,
            'context':selection,'trace_chain':chain,'evidence':evidence,
            'tool_calls':[{'name':'ReadOntology','result':selection},
                          {'name':'ReadTrace','result':{'source_rows':rows,'audit_ids':[a['id'] for a in trace['audits']]}}]}
