"""Short customer answers to the current question, never verified business facts."""
import re

CHANNELS = {
    '我是在官方店铺购买的': 'official_claim',
    '我是在其他平台或商家购买的': 'other_claim',
    '我不确定购买渠道': 'unknown',
    'I bought it from an official store.': 'official_claim',
    'I bought it from another seller or platform.': 'other_claim',
    'I am not sure where it was purchased.': 'unknown',
}


def _answers(case, reply, order=None):
    def items(*pairs):
        return [{'text':zh, 'text_en':en} for zh,en in pairs]
    # Match the actual final reply, so these answer the assistant rather than opening a new FAQ.
    if re.search(r'哪个渠道|什么渠道|哪里买|哪.{0,6}购买|哪.{0,8}(平台|商家)|官方.{0,12}还是|which.{0,25}(store|seller|channel)|where.{0,20}purchas', reply, re.I):
        return items(('我是在官方店铺购买的','I bought it from an official store.'),
                     ('我是在其他平台或商家购买的','I bought it from another seller or platform.'),
                     ('我不确定购买渠道','I am not sure where it was purchased.'))
    if re.search(r'退货.{0,12}原因|想退.{0,12}原因|reason.{0,20}return',reply,re.I):
        return items(('退货原因：不想要了','Return reason: I no longer want it.'),
                     ('退货原因：商品损坏','Return reason: the item is damaged.'),
                     ('退货原因：收到的商品不对','Return reason: I received the wrong item.'))
    if case.get('product_state') == 'CONFLICTED':
        return items(('是扫地机 S1 Pro，型号 T2080','It is the S1 Pro robot vacuum, T2080.'),
                     ('是吸奶器 S1 Pro，型号 T8D04','It is the S1 Pro breast pump, T8D04.'),
                     ('我不知道型号，怎么查看？','I do not know the model. How can I find it?'))
    if re.search(r'哪款|具体.{0,8}型号|what.{0,10}model|which product',reply,re.I):
        skus=list(dict.fromkeys(i.get('SKU') for i in (order or {}).get('order',{}).get('items',[]) if i.get('SKU')))
        return items(*[(f'我说的是 {sku}',f'I mean {sku}.') for sku in skus[:3]],
                     ('我不知道型号，怎么查看？','I do not know the model. How can I find it?'))
    if re.search(r'完好.{0,20}(破损|损坏)|破损.{0,20}完好|intact.{0,20}damaged',reply,re.I):
        return items(('检查过了，配件完好，没有破损','I checked the parts; they are intact.'),
                     ('发现配件有破损','I found damage to a part.'),
                     ('不确定怎么看，能解释一下吗？','I am not sure how to check. Please explain.'))
    if re.search(r'吸力.{0,8}(弱|小).{0,25}(完全|没有)|完全没有吸力.{0,25}吸力.{0,5}弱|weak.{0,25}no suction',reply,re.I):
        return items(('吸力很弱，但不是完全没有','The suction is weak, not completely absent.'),
                     ('完全没有吸力','There is no suction at all.'))
    flow=case.get('active_workflow') or {}
    if flow.get('status') == 'ACTIVE' and case.get('service_intent') == 'troubleshooting':
        return items(('试过了，还是不行',"I tried it, but it didn't work."),
                     ('解决了','Resolved'),('这一步怎么做？','Please explain this step.'))
    if re.search(r'找不到对应部件|locating the part',reply,re.I):
        return items(('找不到对应部件，请解释怎么找','I cannot find the part. Please explain where it is.'),
                     ('不知道怎么操作，请解释','I do not understand how to do this. Please explain.'))
    if case.get('service_intent') == 'shipping' and case.get('order_id'):
        return items(('包裹还没收到','I have not received the package.'),
                     ('只收到部分商品','Only part of my order arrived.'),
                     ('物流单号查不到','The tracking number is not working.'))
    if not case.get('order_id') and re.search(r'订单号|order number',reply,re.I):
        return items(('暂时找不到订单号','I cannot find my order number right now.'),
                     ('在哪里可以找到订单号？','Where can I find my order number?'))
    return []


def choices(case, reply, order=None):
    """Refresh next-turn options from this turn's retrieved ontology graph."""
    data=case.get('followups') or {}
    graph=data.get('ontology') or {}
    nodes={n['id'] for n in graph.get('nodes',[])}
    asked={t['text'].strip() for t in case.get('transcript',[]) if t['role']=='user'}
    result=[]
    seen=set()
    # Keep answers needed by the current guided workflow before related questions.
    answers=[] if data.get('general_support') else _answers(case,reply,order)
    candidates=list(answers)
    candidates += [dict(q) for q in data.get('questions',[])
                   if q.get('source_ids') and all(s in nodes for s in q['source_ids'])]
    for q in candidates:
        zh=re.sub(r'（资料 [^）]+）','',q['text']).strip()
        en=q.get('text_en',q['text'])
        if zh in seen or (q not in answers and (zh in asked or q['text'] in asked or en in asked)):
            continue
        seen.add(zh)
        refs=q.get('source_ids',[])
        result.append(dict(q,text=zh,node_ids=refs or (['case'] if 'case' in nodes else []),
                           ontology_revision=graph.get('revision')))
        if len(result)==3:break
    return result
