"""Build the merchant workbench from all five imported source tables."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from dataset import load_dataset
from attribution import extract_error_codes
from customer_signals import emotion

def snapshot():
 products,orders,dealers,_,tickets,counts=load_dataset()
 raw=json.loads((ROOT/'data/qa-workbooks.json').read_text())
 pns={pn for q in raw for pn in str(q.get('PN','')).split(';')}
 result=[]
 for row in tickets:
  email=row.get('客户首封邮件内容','');sku=row.get('SKU','');pn=sku[:5] if sku[:5] in pns else None
  explicit=re.search(r'(?:Product PN|Produktnummer|Référence du produit|Productnummer)\s*[:：]\s*([A-Z0-9]+)',email,re.I)
  if explicit and explicit.group(1)[:5].upper() in pns:pn=explicit.group(1)[:5].upper()
  date=re.search(r'Submit Date:\s*(\d{4}-\d{2}-\d{2})',email,re.I)
  country=re.search(r'^Country:\s*([A-Z]{2})\s*$',email,re.M)
  oid=str(row.get('订单号') or '').upper();order=orders.get(oid);items=order['items'] if order else []
  matching=[x for x in items if x.get('SKU')==sku]
  result.append({'row':row['原文行号'],'product_line':row.get('产品线') or '未提供','product':row.get('产品名') or '未提供','scenario':row.get('咨询场景') or '未提供','email':email,'sku':sku or None,'pn':pn,'order_no':order['order_id'] if order else None,'order_reference_raw':row.get('订单号'),'complaint_date':date.group(1) if date else None,'region':country.group(1) if country else '未提供','codes':extract_error_codes(email),'emotion':emotion(email),'raw_codes':re.findall(r'(?:Problem Code|Probleemcode|Fehlercode)\s*[:：]\s*(\d{4,8})',email,re.I),'warranty_end':matching[0].get('质保结束日期') if len(matching)==1 else None,'order_rows':[x['原文行号'] for x in items]})
 return {'source_counts':counts,'tickets':result,'orders':list(orders.values()),'knowledge':[{'id':('r-' if 'Robovacs' in q['source_file'] else 'b-')+str(q['source_row']),'row':q['source_row'],'sheet':q['source_file'].removesuffix('.xlsx'),'title':q['Title'],'content':q.get('Content',''),'pn':str(q.get('PN','')).split(';'),'visible':q.get('Status')=='Published' and q.get('Consumer Visible')=='Visible'} for q in raw],'dealers':dealers,'source_trace':[{'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [ROOT/'data/source.json',ROOT/'data/qa-workbooks.json']], 'policy':{'rc4_days_after_expiry':30,'status':'分析窗口，不改变实际质保政策'}}

def build():
 out=ROOT/'reports';out.mkdir(exist_ok=True)
 snap=snapshot();(out/'merchant-snapshot.json').write_text(json.dumps(snap,ensure_ascii=False))
 subprocess.run(['node',str(ROOT/'static/merchant-attribution-agent.js'),str(out/'merchant-snapshot.json'),str(out)],check=True)
 report=json.loads((out/'attribution_report.json').read_text())
 template=Path(__file__).with_name('template.html').read_text().replace('__ASSISTANT__',Path(__file__).with_name('assistant.html').read_text());asset=ROOT/'static/assets/brand/anker-wordmark.png'
 import base64
 html=template.replace('__DASHBOARD__',Path(__file__).with_name('dashboard.js').read_text()).replace('__LOGO__','data:image/png;base64,'+base64.b64encode(asset.read_bytes()).decode()).replace('__REPORT__',json.dumps(report,ensure_ascii=False).replace('<','\\u003c'))
 html=html.replace('__RESPONSIVE_CSS__',(ROOT/'static/responsive.css').read_text())
 (ROOT/'static/analytics.html').write_text(html)
 dest=ROOT.parent/'OntoCare-归因工作台';dest.mkdir(exist_ok=True);(dest/'index.html').write_text(html)
 print(json.dumps({'tickets':len(snap['tickets']),'findings':len(report['findings']),'attributions':len(report['attributions']),'actions':len(report['actions']),'rc_counts':report['rc_counts']},ensure_ascii=False))
if __name__=='__main__':build()
