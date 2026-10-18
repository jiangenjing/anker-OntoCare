"""Adapt the supplied workbook JSON without discarding source rows."""
import json
import re
from pathlib import Path


def load_dataset():
    source = json.loads((Path(__file__).parent / 'data/source.json').read_text())
    sheets = source['sheets']
    tickets = sheets['客诉工单信息']['记录']
    orders, products, knowledge = {}, {}, []
    names = {'T2080': ('S1 Pro 扫地机', 'robot_vacuum', ['s1 pro robot', 's1 pro vacuum', '扫地机']),
             'T8D04': ('S1 Pro 吸奶器', 'breast_pump', ['s1 pro breast pump', '吸奶器', '乳泵']),
             'T2351': ('X10 Pro Omni', 'robot_vacuum', ['x10 pro']),
             'T2352': ('Omni E28', 'robot_vacuum', ['e28']),
             'T2353': ('Omni E25', 'robot_vacuum', ['e25']),
             'T2280': ('Omni C20', 'robot_vacuum', ['c20']),
             'T2292': ('C10', 'robot_vacuum', ['c10']),
             'T8170': ('SoloCam S340', 'camera', ['solocam s340', 's340'])}

    def product(pn):
        if pn not in products:
            name, category, aliases = names.get(pn, (pn, 'other', []))
            products[pn] = dict(id=pn, sku=pn, name=name, category=category, aliases=[pn.lower()] + aliases)
        return products[pn]

    current = None
    for row in sheets['订单信息']['记录']:
        if row.get('订单号'):
            current = row['订单号'].upper()
            orders[current] = dict(order_id=row['订单号'], sku=row.get('SKU', ''),
                order_date=row.get('购买日期'), warranty_until=row.get('质保结束日期'),
                country='', seller='', items=[])
        if current is None:
            raise ValueError('Order continuation row has no parent')
        orders[current]['items'].append(row)
        if row.get('SKU'):
            product(row['SKU'][:5])
    for row in tickets:
        if re.fullmatch(r'[A-Z0-9-]{5,}', row.get('SKU', '')):
            product(row['SKU'][:5])
    qa_rows = json.loads((Path(__file__).parent / 'data/qa-workbooks.json').read_text())
    visible_count = 0
    for sheet in ['eufy Robovacs Q&A', 'eufy Breast Pump Q&A']:
        for row in (r for r in qa_rows if r['source_file'] == sheet + '.xlsx'):
            if row.get('Status') != 'Published' or row.get('Consumer Visible') != 'Visible':
                continue
            visible_count += 1
            for pn in re.findall(r'\b[A-Z][A-Z0-9]{4}\b', row.get('PN', '')):
                product(pn)
                ref = f"{sheet} · 第 {row['source_row']} 行"
                knowledge.append(dict(product_id=pn, fault=ref, fault_name=row['Title'],
                    symptoms=[row['Title']], cause='', steps=[row.get('Content', '')],
                    source_sheet=sheet, source_row=row['source_row']))
    dealers = [dict(country=r['country'], seller_names=[r['seller']], authorized=True)
               for r in sheets['经销商信息']['记录'] if r.get('country') and r.get('seller')]
    summary = dict(tickets=len(tickets), orders=len(orders), order_rows=sum(len(o['items']) for o in orders.values()),
        knowledge=len(qa_rows),
        visible_knowledge=visible_count, dealers=len(dealers), source_file=source['source_file'])
    return list(products.values()), orders, dealers, knowledge, tickets, summary
