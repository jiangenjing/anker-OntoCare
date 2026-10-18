"""Import user bilingual notes as review strategies, not executable policy."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'售后长尾问题双语知识库.json'
OUT=ROOT/'knowledge/long_tail'

def build():
 data=json.loads(SOURCE.read_text());entries=data['entries'];result=[]
 strategies={
 'QA001':'核对购买渠道、适用价保政策和降价证据；不能据补充库确认价保资格、排除条款或自动补偿。',
 'QA002':'通用物流查询可先解释查看发货确认邮件中的跟踪入口；具体包裹状态需实际订单快照，不承诺更新时间。',
 'QA003':'核对地区、商品及购买平台的补贴和开票政策；不推定补贴商品不享受联保，不承诺开票资格。',
 'QA004':'先指引在购买渠道的订单详情查看发票入口；入口未知时确认平台，不编造下载路径。修改发票需人工核查。',
 'QA005':'先区分有线与无线充电设备。可使用已核验官方通用排查资料，无需订单号。不得把无线供电功率、MagSafe或指示灯解释套用到所有充电器。',
 'L011':'先核对订单商品与各包裹物流记录。不能在查询前断言拆为两个包裹、主机或配件已签收，也不能声称已发起调查。',
 'L012':'标签创建不等于已揽收。具体时效与状态需查询，不能承诺几天内更新或已联系承运商。',
 'L013':'具体到货时间需来源记录支持；物流异常可建议人工核查，不声称已经发起调查。'}
 for i,e in enumerate(entries,1):
  pn=e.get('product_pn');pn=pn[:5] if pn else None
  strategy=strategies.get(e['id'],'按同型号和完整错误码检索正式 Q&A，先给有来源的安全排查步骤。无法复现或持续异常时建议人工核查，保修资格需另行核验，不据此确认硬件故障或承诺换新。')
  item={'id':'long-tail-bilingual-'+e['id'],'title':e['question_cn'],'category':'双语补充核查',
        'keywords':list(dict.fromkeys([e['question_cn'],e['question_en']]+e.get('synonyms_cn',[])+e.get('synonyms_en',[]))),
        'pn':pn,'product_specific':bool(pn) or e['id']=='QA005','slots':' / '.join(e.get('ontology_slots',[])),
        'strategy':strategy,'source_file':SOURCE.name,'source_entry':e['id'],'source_index':i,
        'question_en':e['question_en'],'content':f"来源：{SOURCE.name} · entries[{i-1}] · {e['id']}\n中文问题：{e['question_cn']}\n英文问题：{e['question_en']}\n核查策略：{strategy}\n材料为用户补充，不是已核验官方政策。"}
  result.append(item)
 (OUT/SOURCE.name).write_bytes(SOURCE.read_bytes())
 (OUT/'双语补充_检索策略.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 (ROOT/'docs/knowledge/long_tail/双语补充_导入说明.md').write_text(f'# 双语知识库导入\n\n原文件声明 {data.get("total_entries")} 条，实际 entries 为 {len(entries)} 条，全部按真实数量导入。\n原件仅归档，不直接把 response 或 action_boundary 注入模型。运行时加载同目录「双语补充_检索策略.json」；保留双语问题、同义词、源条目 ID、本体槽位和产品过滤。已删除自动赔付、自动换新、未核验时效及通用功率承诺。\n一般排查不要求订单，个案物流/退款/保修核验仍需相应证据。\n')
 print({'declared':data.get('total_entries'),'imported':len(result)})
if __name__=='__main__':build()
