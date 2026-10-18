"""Source-linked descriptive analytics. Signals are not proven causes."""
from collections import defaultdict
from datetime import date
from pathlib import Path
import json,re
from dataset import load_dataset
from qa_workflows import SOURCES,RISK
from customer_signals import emotion_score

ROOT=Path(__file__).parent
PRODUCTS,ORDERS,DEALERS,_,TICKETS,_=load_dataset()
RULES={
 'RC1':{'name':'上下文重复线索','pattern':r'repeat myself|retell|re.upload|解释过|重复描述|从头.*讲','action':'抽查交接记录是否包含已确认信息与附件，核查是否重复索取。','team':'客服系统团队'},
 'RC2':{'name':'政策表述不一致线索','pattern':r'inconsistent|different (?:answer|resolution)|contradict|前后不一致|说法不一','action':'对照同一地区、渠道及生效版本的政策，核查答复差异。','team':'客服运营团队'},
 'RC3':{'name':'产品故障集中线索','pattern':None,'action':'按同型号错误码抽查工单及原始Q&A，先确认复现条件，再评估改进。','team':'产品与技术支持团队'},
 'RC4':{'name':'质保边界争议线索','pattern':r'out of warranty|warranty (?:just )?expired|过保|保修.*到期','action':'补充投诉发生日期、购买凭证和适用政策，人工核查边界；不自动延长质保。','team':'售后政策团队'}}

def extract_error_codes(text):
    numeric = re.findall(r'(?:error\s*(?:code)?|problem\s*code|Fehlercode|Probleemcode|错误码|报错|故障码)\s*[:：#=-]?\s*(\d{4,8})(?!\d)', text, re.I)
    display = re.findall(r'(?<![A-Z0-9])E(?:B[0-9A-Z]{2}|[0-9][0-9A-Z]?)(?![A-Z0-9])', text, re.I)
    # E25/E28 product names require explicit error context or a colon.
    display = [x.upper() for x in display if x.upper() not in ('E25','E28') or re.search(r'(?:error|错误码)\s*[:：]?\s*'+x+r'\b',text,re.I)]
    return list(dict.fromkeys([n for n in numeric if not display or len(n)==4] + display))

def country(address):
    aliases={'United States':'US','United Kingdom':'GB','Germany':'DE','Deutschland':'DE','France':'FR','Netherlands':'NL','Canada':'CA','Australia':'AU','Ireland':'IE','中国':'CN'}
    found={v for k,v in aliases.items() if re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',address,re.I)}
    return next(iter(found)) if len(found)==1 else '未提供'

def source(row):
    return {'id':f'mail-{row["原文行号"]}','url':f'/api/sources/mail-{row["原文行号"]}','label':f'客诉工单信息 · 第 {row["原文行号"]} 行'}

def records():
    result=[]
    for row in TICKETS:
        text=row.get('客户首封邮件内容','');order=ORDERS.get(str(row.get('订单号','')).upper());items=order['items'] if order else []
        sku=row.get('SKU','').strip();pn=sku[:5] if re.match(r'^T[A-Z0-9]{4}',sku) else None
        if not pn:
            explicit=set(re.findall(r'\bT[A-Z0-9]{4}\b',text,re.I));pn=next(iter(explicit)).upper() if len(explicit)==1 else None
        codes=extract_error_codes(text)
        knowledge=[sid for sid,k in SOURCES.items() if pn and pn in k['PN'].split(';') and any(re.search(r'(?<!\w)'+re.escape(c)+r'(?!\w)',k['Title']+' '+k['Content'],re.I) for c in codes)]
        signals=[]
        for rid,rule in RULES.items():
            match=re.search(rule['pattern'],text,re.I) if rule['pattern'] else None
            if match or (rid=='RC3' and codes):signals.append({'rule_id':rid,'label':rule['name'],'evidence':match.group(0) if match else ', '.join(codes),'status':'待核查，非根因结论'})
        countries={country(str(i.get('订单地址',''))) for i in items};region=next(iter(countries)) if len(countries)==1 else '未提供'
        selected=[i for i in items if i.get('SKU')==sku]
        score=emotion_score(text)
        result.append({'row':row['原文行号'],'product':row.get('产品名') or '未提供','product_line':row.get('产品线') or '未提供','scenario':row.get('咨询场景') or '未提供','order':row.get('订单号') or '未提供','sku':sku or '未提供','pn':pn,'email':text,'codes':codes,'region':region,'signals':signals,'knowledge_ids':knowledge,'citation':source(row),'order_sources':[{'id':f'order-{i["原文行号"]}','url':f'/api/sources/order-{i["原文行号"]}'} for i in items],
          'profile':{'customer_id':'未提供','customer_history':'未提供（订单号不是客户身份）','purchase_channel':'未提供','purchase_date':[i.get('购买日期') for i in selected],'warranty_end':[i.get('质保结束日期') for i in selected],'order_status':[i.get('订单状态') for i in selected]},
          'attachments':row.get('附件图片',[]),'emotion':{'score':score,'history_available':False},'safety':bool(re.search(RISK,text,re.I))})
    return result

def pareto(rows,key):
    groups=defaultdict(list)
    for r in rows:
        values=r['codes'] or ['未提供'] if key=='codes' else [r[key]]
        for v in values:groups[v].append(r['row'])
    total=sum(len(v) for v in groups.values());cum=0;out=[]
    for label,ids in sorted(groups.items(),key=lambda x:(-len(x[1]),x[0])):
        cum+=len(ids);out.append({'label':label,'count':len(ids),'rows':ids,'share':len(ids)/total*100 if total else 0,'cumulative':cum/total*100 if total else 0})
    threshold=next((i+1 for i,b in enumerate(out) if b['cumulative']>=80),0)
    return {'key':key,'total':total,'buckets':out,'threshold_categories':threshold,'denominator':'工单-错误码关联数（多码可重复计入，未提供单列）' if key=='codes' else '工单数'}

def recommendation(chart,rows):
    candidates=[b for b in chart['buckets'] if b['label']!='未提供']
    top=candidates[0] if candidates else None
    key=chart['key'];rid={'scenario':'AN-SCENARIO','product':'AN-PRODUCT','product_line':'AN-PRODUCT','codes':'AN-CODE','region':'AN-REGION'}[key]
    actions={'product_line':'按源表产品线核查工单分布，不把产品名当作产品线，不推算故障率。','scenario':'抽查最高频场景的工单，检查是否需要完善信息收集与处理流程。','product':'按该产品聚合症状与错误码，再与技术支持核查；投诉件数不是故障率，缺少销量分母。','codes':'核对该错误码的型号范围与原始Q&A覆盖情况，再评估补充知识或产品调查。','region':'核查该收货国家相关订单和物流记录；收货国家不是经销商所在地，不能据此判定渠道责任。'}
    ids=top['rows'] if top else []
    return {'rule_id':rid,'title':top['label'] if top else '数据不足','action':actions[key] if top else '缺少可识别分类，先补齐源字段，不推导责任。','rows':ids,'knowledge_ids':sorted({k for r in rows if r['row'] in ids for k in r['knowledge_ids']}),'status':'调查建议，未执行'}

def dashboard():
    rows=records();charts=[pareto(rows,k) for k in ['scenario','product','product_line','codes','region']]
    for c in charts:c['recommendation']=recommendation(c,rows)
    return {'records':rows,'charts':charts,'rules':RULES,'scope':'全量工单快照；投诉日期未完整结构化，不能可靠按日/周/月筛选','count':len(rows),'limitations':['没有客户唯一ID','投诉日期覆盖不完整，缺少处理历史','没有销售数量分母','没有退款、换货、维修成本流水','没有工单与经销商关联字段'],'root_counts':{k:sum(any(t['rule_id']==k for t in r['signals']) for r in rows) for k in RULES}}

def report(kind):
    d=dashboard();titles={'daily':'客服日报','weekly':'运营周报','monthly':'产品月报','quarterly':'高管季度报'}
    if kind not in titles:raise ValueError('未知报告类型')
    cs={c['key']:c for c in d['charts']};recs=[c['recommendation'] for c in d['charts']]
    blocks=[{'title':'帕累托变化','text':'投诉日期未完整结构化且缺少历史快照，无法可靠计算本期与上期变化。'},
     {'title':'TOP 3 问题类型','data':cs['scenario']['buckets'][:3]},
     {'title':'TOP 错误码及知识覆盖','data':[dict(b,knowledge_ids=sorted({k for r in d['records'] if r['row'] in b['rows'] for k in r['knowledge_ids']})) for b in cs['codes']['buckets'] if b['label']!='未提供'][:(10 if kind=='monthly' else 3)]},
     {'title':'TOP 3 产品线','data':cs['product_line']['buckets'][:3]},
     {'title':'过保临界点预警','text':'投诉发生日期未完整结构化，不能对全量工单计算与质保结束日期的差值；不使用今天替代。'},
     {'title':'客服效率指标','text':'未提供处理时长、结案结果及多轮情绪，无法计算平均处理时长、一次解决率和情绪升级率。'},
     {'title':'建议行动清单','data':recs}]
    if kind=='daily':blocks=[{'title':'需关注的情绪/安全工单（全量快照）','data':[{'row':r['row'],'product':r['product'],'score':r['emotion']['score'],'safety':r['safety']} for r in d['records'] if r['emotion']['score']>=7 or r['safety']]},{'title':'待人工核查建议','data':recs},blocks[2]]
    if kind=='quarterly':blocks=[{'title':'售后成本与TOP成本SKU','text':'未提供退款、换货和维修流水，无法计算；订单金额是销售金额，不是售后成本。'},{'title':'产品问题集中线索','data':cs['product']['buckets']},{'title':'产品调查建议','data':recs}]
    return {'title':titles[kind]+' · 数据快照预览','scope':d['scope'],'blocks':blocks,'status':'PREVIEW_ONLY','sent':False,'limitations':d['limitations']}

def gaps():
    return [{'id':f'gap-{r["row"]}','question':r['email'][:200],'row':r['row'],'status':'pending_review','suggested_answer':'需人工核验同型号知识后编写；当前不自动生成维修建议。','reason':'明确错误码未匹配同PN公开Q&A' if r['pn'] else '型号未唯一确认，先补型号，不能判定知识缺失'} for r in records() if r['codes'] and not r['knowledge_ids']]
