"""Source-backed presentation choices; never imply demo orders belong to a customer."""
import json
import re
from datetime import date
from pathlib import Path

ROOT=Path(__file__).parent
IMAGES=json.loads((ROOT/'static/product-images/manifest.json').read_text())

def date_key(value):
    try:return date.fromisoformat(str(value).replace('/','-')[:10]).isoformat()
    except (ValueError,TypeError):return ''

def recent_items(orders,pn=None):
    rows=[dict(order_id=o['order_id'],row=r) for o in orders.values() for r in o['items']
          if not pn or str(r.get('SKU','')).startswith(pn)]
    return sorted(rows,key=lambda x:date_key(x['row'].get('购买日期')),reverse=True)

def choices(case,orders,products):
    if case and case.get("general_support"):return []
    if not case:
        result=[]
        for item in recent_items(orders):
            r=item['row'];sku=str(r.get('SKU') or '')
            if sku[:5] not in IMAGES:continue
            result.append(dict(kind='order',order_id=item['order_id'],sku=sku,name=r.get('Product Description') or sku,
                date=r.get('购买日期'),image=IMAGES.get(sku[:5]),source_url='/api/sources/order-'+str(r['原文行号']),
                message=f"我要查询订单 {item['order_id']} 中的商品 SKU {sku}",message_en=f"I am asking about order {item['order_id']}, SKU {sku}."))
        return result
    pn=(case.get('product') or {}).get('id')
    rows=recent_items(orders,pn)
    result=[]
    if not case.get('order_id') and case.get('service_intent') in ('shipping','return','warranty'):
        for item in rows[:3]:
            r=item['row'];sku=r.get('SKU','');result.append(dict(kind='order',order_id=item['order_id'],sku=sku,
                name=r.get('Product Description') or sku,date=r.get('购买日期'),source_url='/api/sources/order-'+str(r['原文行号']),
                image=IMAGES.get(sku[:5]),message_en=f"I am asking about order {item['order_id']}, SKU {sku}.",message=f"我要查询订单 {item['order_id']} 中的商品 SKU {sku}"))
    elif not pn and not case.get('order_id'):
        ids=['T2080','T8D04'] if case.get('product_state')=='CONFLICTED' else list(IMAGES)
        for ident in ids:
            product=next((p for p in products if p['id']==ident),None)
            if not product:continue
            matched=recent_items(orders,ident)
            result.append(dict(kind='product',pn=ident,name=product['name'],date=matched[0]['row'].get('购买日期') if matched else None,
                image=IMAGES.get(ident),message_en=f"My product model is {ident}.",message=f"我的产品是 {product['name']}，型号 {ident}"))
        result.sort(key=lambda x:date_key(x.get('date')),reverse=True)
    return result

def enrich_questions(data,case,orders):
    pn=(case.get('product') or {}).get('id'); oid=case.get('order_id')
    rows=recent_items(orders,None if oid else pn)
    if oid:rows=[x for x in rows if x['order_id'].upper()==oid.upper()]
    new=[]
    intent=case.get('service_intent')
    if intent in (None,'shipping','warranty','return'):
        for item in rows[:3]:
            r=item['row'];order=item['order_id'].upper();sku=r.get('SKU');sid='order-'+str(r['原文行号'])
            if not sku:continue
            zh=f'查询订单 {order} 的 {sku} '+('质保结束日期' if intent=='warranty' else '物流记录')
            new.append(dict(text=zh,text_en=f'Check {"warranty end date" if intent=="warranty" else "shipping record"} for {order}, SKU {sku}',source_ids=[sid]))
            if not any(n['id']==sid for n in data['ontology']['nodes']):
                data['ontology']['nodes'].append({'id':sid,'type':'OrderItem'})
                data['ontology']['edges'].append({'from':'case','to':sid,'relation':'references'})
    seen=set();merged=[]
    for q in new+data['questions']:
        if q['text'] not in seen:merged.append(q);seen.add(q['text'])
    # Only add source-backed generic service questions, never invented tracking claims.
    for zh,en in [('售后核查需要哪些购买凭证？','What purchase evidence is needed?'),('物流记录与实际收到的不一致怎么办？','What if tracking differs from what I received?'),('如何确认产品型号？','How can I confirm the model?'),('如何补充故障照片？','How can I provide a fault photo?'),('如何联系人工复核？','How can I request human review?'),('如何补充完整的物流单号？','How can I provide the full tracking number?')]:
        if len(merged)>=6:break
        if oid:
            zh=f'订单 {oid}：'+zh;en=f'Order {oid}: '+en
        if zh not in seen:merged.append(dict(text=zh,text_en=en,source_ids=['service-rules']));seen.add(zh)
    data['questions']=merged[:6]
    if any('service-rules' in q['source_ids'] for q in data['questions']) and not any(n['id']=='service-rules' for n in data['ontology']['nodes']):
        data['ontology']['nodes'].append({'id':'service-rules','type':'Policy'})
        data['ontology']['edges'].append({'from':'case','to':'service-rules','relation':'references'})
    return data

def diagrams(citations,sources):
    result=[]
    for c in citations:
        row=sources.get(c.get('id'))
        if not row:continue
        for url in re.findall(r'https://[^\s<>"\)]+\.(?:png|jpe?g|webp)(?:\?[^\s<>"\)]*)?',row.get('Content',''),re.I):
            if url not in [x['url'] for x in result]:result.append({'url':url,'title':row['Title'],'source_url':c['url'],'source_label':c['label']})
    return result[:6]
