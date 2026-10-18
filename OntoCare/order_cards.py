"""Presentation snapshots copied from individual source order rows."""
from user_experience import IMAGES
from action_gateway import public_data
FIELDS=['No.','SKU','Product Description','QTY','购买日期','质保结束日期','订单地址','订单状态','物流承运商','物流单号','物流状态','发货日期','订单金额']
def build(order):
 if order.get('status')!='FOUND':return None
 data=order['order']
 return {'order_id':data['order_id'],'kind':'source_snapshot','ownership_verified':False,
         'items':[{'image':IMAGES.get(str(row.get('SKU',''))[:5]),'fields':public_data({key:row.get(key) for key in FIELDS}),'redacted_fields':['订单地址'],'source_row':row['原文行号'],
                   'source_url':f'/api/sources/order-{row["原文行号"]}'} for row in data['items']]}
