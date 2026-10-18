"""Re-traverse case -> product/order -> public evidence after every answer."""
import re
import qa_workflows as qa


def localized_title(title, pn, sid):
    """Create a Chinese question from source topic/code; leave original English for EN."""
    if re.search(r'[\u4e00-\u9fff]', title):
        return title, f'How can I get help with {pn}? (Reference {sid})'
    code = re.search(r'(?:error|code)\s*[:#]?\s*((?:[0-9]{4}|E[A-Z0-9]{1,4})(?:/[0-9]{4})*)', title, re.I)
    if not code:
        code = re.search(r'\b(E(?:B[A-Z0-9]{1,3}|(?!25\b|28\b)[0-9][A-Z0-9]{1,3}))\b', title, re.I)
    if code:
        return f'{pn} 出现错误码 {code.group(1)}，应该如何排查？', title
    specific = [(r'does not perform base station tasks', '基站不集尘、不洗拖布或不烘干，怎么办？'),
                (r'stuck.*(?:rug|carpet)|snap carpet', '卡在地毯或地垫上不动，怎么办？'),
                (r'always shows offline', '一直显示离线，怎么办？'),
                (r"can.t connect to wifi|lost wifi connection", '连不上 Wi-Fi 或频繁离线，怎么处理？')]
    for pattern, question in specific:
        if re.search(pattern, title, re.I):
            return f'{pn} {question}', title
    topics = [(r'charg|battery', '充电或电池'), (r'suction', '吸力'),
              (r'wi.?fi|bluetooth|connect', '网络或连接'), (r'clean|wash', '清洁维护'),
              (r'water|tank|drain', '水箱或供排水'), (r'map|navigat', '地图或导航'),
              (r'noise|sound', '声音'), (r'firmware|updat', '固件更新'),
              (r'flange|nipple|breast', '吸乳使用'), (r'serial', '序列号'),
              (r'sensor|laser', '传感器'), (r'dry', '烘干'), (r'roller|brush', '滚刷'),
              (r'error|fault', '故障排查'), (r'install|set.?up', '安装设置')]
    topic = next((zh for pattern, zh in topics if re.search(pattern, title, re.I)), '使用方法')
    return f'{pn} 的{topic}需要注意什么？（资料 {sid}）', title


def refresh(case, text, citations, order):
    pn = (case.get('product') or {}).get('id')
    intent = case.get('service_intent')
    asked = {t['text'].strip() for t in case.get('transcript', []) if t['role'] == 'user'}
    asked.add(text.strip())
    questions, nodes, edges = [], [], []
    nodes.append({'id':'case', 'type':'ServiceCase'})
    def node(ident, kind):
        if not any(n['id']==ident for n in nodes):
            nodes.append({'id':ident,'type':kind});edges.append({'from':'case','to':ident,'relation':'references'})
    def add(zh, en, refs):
        if zh not in asked and en not in asked and not any(q['text']==zh for q in questions):
            questions.append({'text':zh,'text_en':en,'source_ids':refs})
    if pn:
        node(pn,'Product')
    if intent == 'shipping':
        # Re-read the current order's items, never reuse the previous product's FAQ.
        if order['status'] == 'FOUND':
            oid=case['order_id'];node(oid,'Order')
            for item in order['order']['items']:
                sid='order-'+str(item['原文行号']);node(sid,'OrderItem')
                sku=item.get('SKU')
                if sku:
                    add(f'订单 {oid} 的 {sku} 发货了吗？',f'Has {sku} in order {oid} shipped?',[sid])
            add(f'订单 {oid} 的物流记录和我实际收到的不一致，怎么办？',f'The tracking record for {oid} differs from what I received. What should I do?',['service-rules'])
            add(f'订单 {oid} 的物流单号查不到，怎么核对？',f'Tracking for order {oid} is not working. How can I check it?',['service-rules'])
        else:
            add('查询物流需要提供什么订单信息？','What order information is needed to check shipping?',['service-rules'])
    elif re.search(qa.RISK,text,re.I) or intent == 'return':
        add('人工核查需要准备哪些材料？','What information should I prepare for human review?',['service-rules'])
        add('我想申请售后，需要提供什么购买凭证？','What proof of purchase is needed for after-sales support?',['service-rules'])
    elif pn:
        query=text
        if len(text)<25 and case.get('last_issue'):
            query=case['last_issue']+' '+text
        # A fresh retrieval is performed even when this answer used a fixed workflow.
        refs=qa.retrieve(pn,query,limit=6)
        matched=[c['id'] for c in citations if c['id'] in qa.SOURCES and pn in qa.SOURCES[c['id']]['PN'].split(';')]
        for sid in matched:
            refs.extend(qa.retrieve(pn,qa.SOURCES[sid]['Title'],limit=3))
        refs=list(dict.fromkeys(matched+refs))
        for sid in refs:node(sid,'KnowledgeItem')
        flow=case.get('active_workflow')
        if flow and flow['status']=='ACTIVE':
            for i in range(flow['cursor'],min(len(flow['steps']),flow['cursor']+3)):
                add(f'请解释第{i+1}步：怎么做？',f'Please explain step {i+1}.',matched or refs[:1])
        for sid in refs:
            title=qa.SOURCES[sid]['Title']
            zh_title,en_title=localized_title(title,pn,sid)
            add(zh_title,en_title,[sid])
        if not questions:
            add(f'{pn} 需要提供哪些故障信息？',f'What fault details should I provide for {pn}?',['service-rules'])
    else:
        add('如何确认我的产品型号？','How can I confirm my product model?',['service-rules'])
        add('查询订单需要提供什么信息？','What information is needed to look up an order?',['service-rules'])
    for c in citations:
        if c.get('kind') == 'strategy':node(c['id'],'ReviewStrategy')
    selected=questions[:6]
    if any('service-rules' in q['source_ids'] for q in selected):node('service-rules','Policy')
    return {'questions':selected,'ontology':{'revision':case.get('turn_count',0),'query':text,'product':pn,'intent':intent,
            'nodes':nodes,'edges':edges,'retrieved_count':sum(n['type']=='KnowledgeItem' for n in nodes)}}
