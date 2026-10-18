"""Recover complete JSON entries and build a bounded review-strategy index."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1])
raw=source.read_text(); decoder=json.JSONDecoder(); pos=raw.index('[',raw.index('"entries"'))+1; rows=[]
while True:
    while pos<len(raw) and raw[pos] in ' \n\r\t,':pos+=1
    if pos>=len(raw) or raw[pos]==']':break
    try: row,end=decoder.raw_decode(raw,pos)
    except ValueError:break
    rows.append(row);pos=end
folder=ROOT/'knowledge/long_tail'
(folder/'长尾问题_原始输入_不参与检索.json').write_text(raw)
logistics=[
'先按当前订单逐件核对 SKU 与全部物流单号，区分配件包和主机；询问未收到的是哪一件。不得借用示例订单及签收日期。',
'核对当前单号的标签创建、揽收及后续扫描记录；无实时承运商查询时说明仅有资料快照，不承诺揽收时限。',
'核对当前包裹最新扫描和原预计日期，区分预计与保证送达；过期时建议商家向承运商核查，不声称已发起查询。',
'核对退回寄件人的记录与退款状态，先询问希望重新寄送还是申请退款；退款资格与实际执行需商家审核。',
'核对主机与配件是否分开发货及已确认的预售日期；缺失日期显示未提供，取消及退款需核验渠道规则。',
'订单查无不等于取消。请确认订单号或购买渠道，并提供遮盖无关个人信息的购买凭证供核查。',
'拆单逐包裹核对状态，先确认未收到的商品或单号；单个包裹签收不能推断整单签收，也不能直接认定丢失。',
'区分物流记录签收与客户实际收到；确认对应包裹及地址是否正确，建议商家核查投递凭证，不承诺调查时效。',
'核对购买渠道是否支持指定承运商；未有对应政策时不能承诺指定、备注已提交或仓库会采纳。',
'先核对订单及发货状态，判断是否需商家评估改址或承运商改派；不保证成功，不声称地址已修改。']
overrides={
'R031':'不得建议用胶带绕过传感器。核对污水箱安装与具体错误码，无法恢复时交技术支持核验。',
'R037':'电池相关问题先确认型号、错误码及是否有异常发热；不指导用户拆卸电池，交技术支持核验。',
'R045':'先核对设备铭牌与供电环境；电压不匹配时不要继续通电，不自行建议改装或稳压器方案。',
'B009':'异常过热先停止使用和充电，待技术支持核验后决定后续处理，不把过热直接判断为正常。',
'B010':'出现熔化先停止使用和充电，保存故障照片交人工核查，不推断是客户消毒不当造成。',
'B011':'烧焦味按潜在安全异常处理，停止使用和充电并交人工核查，不用新品气味解释或建议继续测试。',
'B014':'疼痛或出血时停止使用，转人工支持；持续不适建议寻求专业医疗帮助，不指导继续加大吸力。',
'B018':'按购买国家、渠道、日期、部件类型核实适用质保政策；本补充材料中的期限未核验，不作为客户资格结论。',
'B019':'核对购买渠道、地区、日期及开封使用状态，再核验适用退货政策；不得直接套用本材料中的天数或保证退款。',
'C011':'先核对检测类型、固件和发生条件；如需提交片段，应征得用户同意并遮盖无关个人信息，不声称用于训练或已经上传。',
'C012':'先核对型号、HomeBase 兼容性与对应官方功能说明，再判断是否支持人脸识别；未核验前不承诺识别距离或效果。'}
entries=[]
for row in rows:
    ident=row['id']; strategy=overrides.get(ident)
    if row['category']=='logistics':strategy=logistics[int(ident[1:])-1]
    if not strategy:
        parts=re.split(r'(?<=[。；;])',row['response_cn'])
        parts=[s for s in parts if not re.search(r'换新|寄送|更换污水箱|提供保修|属于硬件|需更换电池|主机需维修|安排|转交',s)]
        strategy='用户补充资料的待核验排查候选：'+''.join(parts).strip()+' 请先核对型号和对应原始 Q&A；未被原始资料支持的参数、故障归因及操作，不作为确定结论。'
    item={'id':'long-tail-json-'+ident,'title':row['question_cn'],'category':row['category'],
      'keywords':list(dict.fromkeys([row['question_cn'],row['question_en']]+row.get('synonyms_cn',[])+row.get('synonyms_en',[]))),
      'slots':', '.join(row.get('ontology_slots',[])), 'pn':row.get('product_pn') or '',
      'error_code':row.get('error_code'),'product_specific':bool(row.get('product_pn')),
      'strategy':strategy,'source_entry':ident,'source_file':'长尾问题.json','evidence_level':'USER_SUPPLIED_UNVERIFIED'}
    if item['error_code']:item['keywords']+=re.findall(r'[A-Z]*\d+[A-Z]*',str(item['error_code']))
    item['content']=f"长尾问题.json · entries[{ident}]\n问题：{item['title']}\n适用 PN：{item['pn'] or '不限'}\n核查策略：{strategy}\n来源等级：用户补充，未独立核验；不是订单事实或官方承诺。"
    entries.append(item)
(folder/'长尾问题_检索策略.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2))
report={'source':'长尾问题.json','sha256':hashlib.sha256(raw.encode()).hexdigest(),'declared_entries':290,'recovered_complete_entries':len(entries),'truncated':pos<len(raw) and raw[pos]!=']','excluded_partial_entry':'C015','note':'原文未修改；只接入完整记录。模板订单、承诺及高风险操作已隔离或改写。'}
(folder/'导入审计.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
(ROOT/'docs/knowledge/long_tail/JSON补充策略库.md').write_text('# JSON 补充长尾策略\n\n仅供核查，不代表已确认官方政策。原文件截断，恢复119条，C015及后续未导入。\n\n'+'\n\n'.join('## '+i['id']+'\n\n'+i['content'] for i in entries))
print(json.dumps(report,ensure_ascii=False))
