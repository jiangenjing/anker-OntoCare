"""Demo-only source-backed order suggestions; product matching is not ownership verification."""
from user_experience import recent_items, IMAGES

def candidates(case, orders):
    pn=(case.get('product') or {}).get('id')
    if not pn or case.get('order_id') or case.get('order_candidates_declined'):
        return []
    result=[]
    for item in recent_items(orders,pn):
        row=item['row'];sku=str(row.get('SKU') or '')
        result.append({'kind':'order','order_id':item['order_id'],'sku':sku,
            'name':row.get('Product Description') or sku,'date':row.get('购买日期'),
            'source_url':'/api/sources/order-'+str(row['原文行号']),
            'source_id':'order-'+str(row['原文行号']),'image':IMAGES.get(sku[:5]),
            'message':f"我要查询订单 {item['order_id']} 中的商品 SKU {sku}",
            'message_en':f"I am asking about order {item['order_id']}, SKU {sku}.",
            'scope':'demo_dataset','ownership_verified':False})
    return result

def resolve_conflict(case, order, target):
    if not target or order.get('status')!='FOUND':return False
    if any(str(row.get('SKU','')).startswith(target['id']) for row in order['order']['items']):return False
    case['order_conflict']={'order_id':case.get('order_id'),'expected_product':target['id']}
    for key in ('order_id','selected_sku','selected_tracking','within_30d','last_order_card'):
        case.pop(key,None)
    case.update(product=target,product_state='CONFIRMED',warranty='UNKNOWN',dealer='UNKNOWN')
    return True
