import collections,csv,hashlib,json,re,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import qa_workflows as qa
rows=qa.RAW;public=list(qa.SOURCES.values())
groups={
 '错误码与部件异常':r'\berror\b|warning|anomal|malfunction',
 '充电、电池与供电':r'charg|battery|power on|turn on|powering on',
 '联网、离线与App连接':r'wi.?fi|offline|connect|pair|bluetooth',
 '清扫、吸力、滚刷与拖地':r'suction|brush|mop|cleaning performance|vacuuming',
 '录像、检测与通知':r'record|motion|detect|notification|live.?view|stream',
 '清洁、消毒与耗材维护':r'clean.*(?:filter|parts|flange)|steriliz|dishwash|microwave|maintenance',
 '基站回充与定位地图':r'dock|return.*station|map|navigation|position',
 '吸奶、漏奶、佩戴与法兰':r'milk|flange|nipple|pumping|breast shield',
 '固件、日志与重置':r'firmware|\blogs?\b|reset',
 '规格、兼容性与功能支持':r'specification|compatible|support|difference|size|weight|lifespan',
 '退换货与质保':r'refund|return policy|warranty',
 '安全与身体不适':qa.RISK,
}
counts={k:sum(bool(re.search(p,r['Title'],re.I)) for r in public) for k,p in groups.items()}
normalized=collections.defaultdict(list)
for r in public:
 normalized[re.sub(r'\s+',' ',r['Content'].strip().lower())].append(r)
dups=[v for v in normalized.values() if len(v)>1]
tickets=json.loads((BASE/'data/source.json').read_text())['sheets']['客诉工单信息']['记录']
hits=[]
for t in tickets:
 pn=t.get('SKU','')[:5]
 hit=qa.cached_answer(pn,t['客户首封邮件内容'],'en')
 if hit:hits.append((t['原文行号'],pn,hit['topic']))
print(json.dumps({'taxonomy':counts,'exact_content_duplicate_groups':len(dups),'rows_in_duplicate_groups':sum(map(len,dups)),'ticket_keyword_hits':len(hits),'ticket_hits':hits},ensure_ascii=False,indent=2))
report=['# 常见问题缓存与工作流整理',
 '\n## 结论',
 '第一批采用 23 个审核后的固定工作流，按型号拆成 25 个“型号 × 问题类型”键，中英文各有固定答复。命中时不会调用 LLM，包括意图识别也不调用。',
 '这里实现的是应用层 FAQ / 工作流缓存。缓存键包括 PN、问题类型、语言、版本和源文件摘要；不是模型推理内部的 KV Cache。',
 '\n## 原始资料',
 '- eufy Robovacs Q&A.xlsx：Sheet1，593 条记录，D2:E594；全部为公开记录。',
 '- eufy Breast Pump Q&A.xlsx：Sheet1，282 条记录，D2:E283；其中 3 条不可见，已从检索和引用入口排除。',
 '- 第二份文件含吸奶器和 SoloCam 摄像头内容；按 PN 隔离，不按文件名推断产品。两表合计 875 条、公开 872 条。',
 f'- 对全部公开正文做空白归一化后，发现 {len(dups)} 组完全相同正文，涉及 {sum(map(len,dups))} 行。相同正文不等于不同产品可共用规则。',
 '\n## 二八优先级的依据与边界',
 '表格没有真实用户咨询频次，因此不能证明 20% 的问题覆盖 80% 的流量。以下是对全部标题的主题扫描，允许一行属于多个主题，数量不能相加成总数；它反映知识库覆盖面，不代表工单发生频率。',
 '|主题|公开问答标题命中数|', '|---|---:|']
for k,v in sorted(counts.items(),key=lambda kv:kv[1],reverse=True):report.append(f'|{k}|{v}|')
report+=['',f'对已有 63 条工单用相同关键词规则做保守扫描，{len(hits)} 条命中第一批缓存候选；这是静态候选命中数，并非人工确认的回答正确率或线上覆盖率。复合问题、长邮件、未覆盖型号会降低命中率，不能为了提高比例放宽到跨型号复用。',
 '\n## 第一批固定答复清单', '|型号|问题类型|来源（原始 Excel 行）|', '|---|---|---|']
for e in qa.CACHE['entries']:
 report.append('|'+e['pn']+'|'+e['topic']+'|'+'；'.join(f"{x['file']} / {x['sheet']}!D{x['row']}:E{x['row']}" for x in e['sources'])+'|')
report+=['\n## 可直接沉淀的规律',
 '1. 明确型号 + 单一症状 + 稳定操作步骤：如电源检查、接点对齐、频段设置。先确认型号，再匹配；同名 S1 Pro 必须区分扫地机和吸奶器。',
 '2. 相同问题的不同说法：无法开机/开不了机/won’t turn on；无吸力/吸力弱/weak suction；按受控同义词归一化，不做任意相似度缓存命中。',
 '3. 公开且明确的能力问答：例如 S340 不支持 24/7 连续录像，以及吸奶器可水洗配件仅可放洗碗机上层、不可微波消毒。',
 '4. 每个答复绑定来源单元格、型号、语言和版本。更改原文或源文件摘要将使该条固定缓存不再命中，需重新审核再生成。',
 '\n## 不应固定为确定答案的情况',
 '- S1 Pro 序列号位置：Robovacs 第 6 行与第 19 行互相矛盾，系统返回两条引用并要求核实。',
 '- 退款/换货/质保资格、订单归属和实时物流：使用订单事实与规则查询，不缓存个人结论。',
 '- 伤害、烫伤、出血、过敏、冒烟等：进入人工核查，不作为普通排障缓存。',
 '- 多故障混合、具体环境变化、资料未覆盖型号、内部不可见条目：不强行套模板。',
 '- 泛化主题不能直接作为答案。例如 Wi-Fi 问题不等于任意 Wi-Fi 6/WPA3/企业网络兼容性问题。',
 '\n## 回复路径',
 '本地确认型号与会话 → 订单/安全/退换规则 → 已审核 FAQ 缓存 → 同型号资料检索 → 有依据时调用 LLM → 校验来源 ID 和执行承诺 → 回复与引用。',
 '模型文风：先直接回应，再给至多 3 个简短步骤，必要时补一个澄清问题；仅使用提供资料，不编造参数或声称已办理退款。生成答复不会自动进入长期缓存，以免把错误固化。',
 '每轮保留可展开的流式处理状态与核对摘要。它们来自实际执行节点，不展示模型内部逐字思维链，也不人为延时。',
 '产品知识引用链接可打开原始标题、正文、文件名与单元格；订单回复引用原始行；澄清/规则回复明确标注会话与规则依据，不伪造产品资料来源。',
 '\n## 验证与限制',
 '测试覆盖 25 个缓存键 × 2 种语言且配置模型时仍零调用、同名消歧、资料变更失效、不可见来源拒绝访问、引用非法时降级、模型失败降级，以及流式与物流回归。',
 '当前本地服务未配置可用模型。长尾分支已用模拟响应和失败情况验证，尚未做真实付费 API 端到端测试；未配置或调用失败时返回有引用的资料原文。中文长尾检索目前基于关键词，不等于完整语义检索。',
 '后续应按匿名的“型号/问题类型/命中与否/用户反馈”统计实际高频问题，再扩充审核模板；本次没有新增采集或外传用户会话。',
 '\n## 更新方式',
 'data/qa-workbooks.json 保存两份工作簿的原始提取值及源文件摘要；data/faq-cache.json 保存固定答复。scripts/build_qa_cache.py 是可复现的模板构建入口，修改模板后必须运行测试。qa_workflows.py 实现命中和检索，app.py 实现路由、模型回退、流式事件与引用。']
(BASE/'docs/architecture/faq-cache.md').write_text('\n\n'.join(report))
with (BASE/'data/qa-topic-index.csv').open('w',newline='') as f:
 writer=csv.writer(f);writer.writerow(['file','sheet','row','PN','title','visible','topics'])
 for r in rows:writer.writerow([r['source_file'],r['source_sheet'],r['source_row'],r['PN'],r['Title'],r['Consumer Visible'],';'.join(k for k,p in groups.items() if re.search(p,r['Title'],re.I))])
