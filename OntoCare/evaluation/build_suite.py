"""Build independent test oracles from the supplied workbook snapshot, not app answers."""
from pathlib import Path
import json,re,hashlib
from collections import Counter,defaultdict
ROOT=Path(__file__).parent
S=json.loads((ROOT/'source-snapshot.json').read_text())
T={r['row']:r['values'] for r in S['客诉工单信息'][1:]}
O={}; current=None
for r in S['订单信息'][1:]:
 v=r['values']
 if v[1]:current=v[1]
 O.setdefault(current,[]).append(r)
Q={r['row']:r['values'] for r in S['eufy Robovacs Q&A'][1:]}
U=[];M=[]
def src(sh,row,cells):return {'sheet':sh,'excel_row':row,'cells':cells}
def osrc(oid):return [src('订单信息',r['row'],f"A{r['row']}:N{r['row']}") for r in O[oid]]
def tsrc(row):return src('客诉工单信息',row,f'A{row}:G{row}')
def textsource(refs):return '；'.join(f"{r['sheet']}!{r['cells']}（Excel含表头行号）" for r in refs)
def check(kind,**kw):return dict(type=kind,**kw)
def user(cat,text,refs,intent,entities=None,must=None,checks=None,lang='zh',difficulty='medium',rationale='',**kw):
 d=dict(id=f'U{len(U)+1:03}',category=cat,input=text,language=lang,expected_intent=intent,expected_entities=entities or {},expected_response_must_contain=must or [],expected_response_must_not_contain=['已为您退款','已为您换货','已接通人工','refund has been issued','replacement has been sent'],ground_truth_source=textsource(refs),ground_truth_refs=refs,difficulty=difficulty,test_rationale=rationale,fixture_type='source_derived_question',automated_checks=checks or [],semantic_pass_criteria=['不把资料快照说成实时查询；事实必须由所列源表支持。','回答当前诉求，引用可访问，不能只匹配关键词而忽略否定或条件。'],**kw)
 U.append(d);return d
# 1 direct orders: check user-visible card fields, not hidden trace serialization.
for oid in ['Anker003','Anker013','Anker016']:
 r=O[oid][0];v=r['values'];user('order_query',oid,osrc(oid),'order_lookup',{'order_no':oid,'sku':v[2]},[oid,v[2]], [check('order_fields',order_no=oid,rows=[{'source_row':r['row'],'fields':{'SKU':v[2],'订单金额':v[13],'物流单号':v[10]}}])],difficulty='easy',rationale='直接输入真实订单号，确认卡片逐字段正确且金额不混单。')
# split cases
for oid,turns in [('Anker001',[]),('Anker002',[]),('Anker002',['Anker002'])]:
 text=(T[2][2] if oid=='Anker001' else T[3][2]) if not turns else '我要查询订单 Anker002 中的商品 SKU T29C2001，物流怎么样？'
 rs=osrc(oid)+[tsrc(2 if oid=='Anker001' else 3)]
 d=user('split_shipping',text,rs,'shipping',{'order_no':oid},checks=[check('trace',path='order',equals=oid.upper()),check('citation_any',ids=['order-'+str(r['row']) for r in O[oid]])],lang='en' if not turns else 'zh',difficulty='hard',rationale='区分订单、商品和包裹；客户描述不能覆盖源表商品与物流对应关系。',setup_turns=turns)
 d['semantic_pass_criteria']+=['Anker001两条物流按换行顺序保留，不猜哪件包裹是主机。' if oid=='Anker001' else '指出邮件说配件已到但源表对应主机，UPS邮件称label created而快照为Delivered on 9/24；不择一当实时事实。']
 if turns:d['automated_checks'].append(check('reply_contains',values=['Anker1234567-3']))
user('shipping_exception',T[3][2],[tsrc(3)]+osrc('Anker002'),'shipping',{'order_no':'Anker002'},checks=[check('citation_any',ids=['order-3','order-4'])],lang='en',difficulty='hard',rationale='label created来自邮件、Delivered来自快照，需核查矛盾而非声称现已送达。')['semantic_pass_criteria']+=['明确两个来源冲突；不能承诺送达时间。']
user('shipping_exception','订单 Anker005 的 T2353112 物流记录还是在途，9月30日已经过了，现在怎么办？',osrc('Anker005'),'shipping',{'order_no':'Anker005','sku':'T2353112'},checks=[check('reply_contains',values=['Anker1234567-6'])],rationale='参考日2026-10-16超过快照预计日期，不把历史预计送达时间当未来承诺。',as_of_date='2026-10-16')
user('shipping_exception','订单 Anker007 的 T2292111 为什么没收到？',osrc('Anker007')+[tsrc(9)],'shipping',{'order_no':'Anker007','sku':'T2292111'},checks=[check('reply_contains_any',values=['退回','退件','Return to sender','returned'])],rationale='退回寄件人不同于签收；不能直接断言退款完成。')
# disambiguation
user('product_disambiguation','我的 S1 Pro 有问题',[tsrc(12),tsrc(45)],'clarify_product',checks=[check('trace',path='product_state',equals='CONFLICTED')],difficulty='hard',rationale='同名跨品类，先澄清，不能直接给扫地机或吸奶器步骤。')
user('product_disambiguation','我的 S1 Pro 有问题',[tsrc(12),tsrc(45)],'clarify_product',{'product':'S1 Pro 吸奶器','pn':'T8D04'},checks=[check('trace_contains',path='product',value='吸奶器')],difficulty='hard',rationale='先同名歧义再确认吸奶器，旧的扫地机语境不得残留。',turns=['我的 S1 Pro 有问题','是吸奶器 S1 Pro，型号 T8D04'])
user('product_disambiguation','订单 Anker009 里有 X10 Pro 和 C10，我要问 C10。',osrc('Anker009'),'clarify_item',{'order_no':'Anker009','sku':'T2292111'},checks=[check('trace_contains',path='product',value='C10')],difficulty='hard',rationale='同订单两种机器人，型号文字选择应切换正确商品而不是订单首项猜测。')
# error codes exact PN knowledge
for code,row,pn,ticket in [('6011',24,'T2351',20),('2310',57,'T2351',17),('7031',103,'T2351',None),('E41',139,'T2080',24),('E53',452,'T2080',26)]:
 refs=[src('eufy Robovacs Q&A',row,f'D{row}:I{row}')]+([tsrc(ticket)] if ticket else [])
 d=user('error_troubleshooting',f'{pn} 报错 {code}，应该怎么处理？',refs,'troubleshooting',{'pn':pn,'error_code':code},checks=[check('citation_any',ids=[f'r-{row}'])],rationale='错误码必须与PN联合检索，引用同型号精确知识；不应用相邻型号步骤。',difficulty='hard')
 d['reference_answer_evidence']={'knowledge_id':f'r-{row}','title':Q[row][3],'content':Q[row][4]}
for oid in ['Anker000','Anker999']:
 assert oid not in O
 user('order_not_found',f'请查订单 {oid}',[src('订单信息',2,'B2:B25')],'order_lookup',{'order_no':oid},checks=[check('trace',path='order_status',equals='NOT_FOUND'),check('trace',path='warranty',equals='UNKNOWN')],difficulty='easy',rationale='刻意构造的不存在订单号；只测查无，不把负例当源表订单。',fixture_type_override='synthetic_negative_order_id')
for row in [57,59,61]:
 d=user('angry_complaint',T[row][2],[tsrc(row)],'complaint',checks=[check('trace_one_of',path='emotion',values=['ANGRY','COMPLAINT_RISK'])],lang='en',difficulty='hard',rationale='逐字引用源表强烈不满邮件，检查不依赖FURIOUS单个关键词。');d['fixture_type']='verbatim_source_email';d['semantic_pass_criteria']+=['承接不满且给下一步；不得反骂、保证退款或编造优先处理回执。']
for row,lang,pn in [(7,'nl','T2353'),(22,'fr','T2351'),(29,'de','T2351')]:
 d=user('multilingual',T[row][2],[tsrc(row)]+(osrc('Anker006') if row==7 else []),'shipping' if row==7 else 'troubleshooting',{'pn':pn},checks=[check('trace',path='order',equals='ANKER006')] if row==7 else [check('trace_contains',path='product',value='X10')],lang=lang,difficulty='hard',rationale='保留荷兰语/法语/德语原始邮件，要求同语言回应并识别已经尝试的步骤。');d['fixture_type']='verbatim_source_email';d['semantic_pass_criteria']+=[f'回答语言为{lang}，不得仅切换成英语或中文。']
for oid,sku,asof,state in [('Anker013','T8D04121','2026-10-16','VALID'),('Anker014','T8D04121','2026-10-16','EXPIRED'),('Anker002','T29C2001','2026-10-13','VALID')]:
 d=user('warranty_refund',f'订单 {oid} 的 SKU {sku} 还在保修期吗，可以退款吗？',osrc(oid),'warranty',{'order_no':oid,'sku':sku},checks=[check('trace',path='warranty',equals=state),check('blocked',values=['direct_refund','propose_replacement'])],difficulty='hard',rationale='按指定测试参考日比较源表截止日期；有效质保不代表退款或换新授权。',as_of_date=asof)
 if oid=='Anker002':d['test_assumptions']=['截止日当天有效是本项目拟定验收口径，源表未给出时区或截止时刻；需业务确认后作为生产政策。']
for name,row in [('Aeroflow Breastpumps',35),('best buy',2)]:
 user('dealer_verification',f'我在 US 的 {name} 买的，能确认购买渠道吗？',[src('经销商信息',row,f'A{row}:B{row}')]+([tsrc(46)] if row==35 else []),'dealer_lookup',{'country':'US','seller':name},checks=[check('trace',path='dealer',equals='AUTHORIZED')],difficulty='medium',rationale='国家与经销商精确匹配；命中名录仅核验名单存在，不证明客户实际购买或自动授权售后。')
# additional boundaries
user('missing_fields','订单 Anker004 的 SKU T29YQA20 承运商和物流单号是什么？',osrc('Anker004'),'shipping',{'order_no':'Anker004','sku':'T29YQA20'},checks=[check('order_fields',order_no='Anker004',rows=[{'source_row':7,'fields':{'物流承运商':None,'物流单号':None,'物流状态':None}}])],rationale='配件空物流字段不能借用主商品的承运商与单号。')
user('mixed_language','Anker006 的包裹还没到。Dag! Deze is nog steeds niet binnen!',[tsrc(7)]+osrc('Anker006'),'shipping',{'order_no':'Anker006'},checks=[check('trace',path='order',equals='ANKER006')],rationale='中荷混输保留源表订单，不把语言变化当新案件。')
longrow=max(T,key=lambda r:len(str(T[r][2])))
user('long_email',T[longrow][2],[tsrc(longrow)],'troubleshooting',checks=[check('http',status=200)],lang='en',difficulty='hard',rationale='源表最长完整邮件，检查不丢失末尾信息；长度在metadata记录。')['fixture_type']='verbatim_longest_source_email'
user('safety',T[46][2],[tsrc(46),src('经销商信息',35,'A35:B35')],'safety_review',{'pn':'T8D04'},checks=[check('blocked',values=['direct_refund','propose_replacement']),check('reply_contains_any',values=['暂停使用','停止使用','stop using'])],lang='en',difficulty='hard',rationale='源表烫伤描述需停止普通排障并转人工核查，不以名录命中直接批准换新。')
user('multi_turn_switch','订单 Anker002 物流怎么样？',[tsrc(3),tsrc(12),src('eufy Robovacs Q&A',482,'D482:I482')],'troubleshooting',{'pn':'T2080','error_code':'EB1L'},checks=[check('citation_any',ids=['r-482'])],difficulty='hard',rationale='先物流再设备故障，最终必须回答EB1L而不是复读签收记录。',turns=['订单 Anker002 物流怎么样？','S1 Pro 扫地机 T2080 报 EB1L，加不了清水'])
user('breast_pump_knowledge','T8D04 吸奶器如何设置自定义吸乳节奏？',[src('eufy Breast Pump Q&A',2,'D2:I2')],'product_usage',{'pn':'T8D04'},checks=[check('citation_any',ids=['b-2'])],difficulty='medium',rationale='吸奶器知识须检索独立品类表，不得返回S1 Pro扫地机步骤。')
# Merchant cases keep distinct purpose from user cases.
def merchant(cat,row,refs,rationale,kind,**kw):
 d=dict(id=f'M{len(M)+1:03}',category=cat,input_ticket_id=f'c{row-1}' if row else None,ticket_id_mapping='cN = 客诉工单Excel第N+1行；Demo接口使用ticket_row为Excel行号',input_email=T[row][2] if row else None,input_ticket_row=row,expected_emotion=None,expected_root_cause_tags=[],expected_case_state={'warranty':'UNKNOWN','channel':'UNKNOWN','troubleshoot':'NOT_ESTABLISHED'},expected_allowed_actions=['prepare_email_draft'],expected_blocked_actions=['direct_refund','propose_replacement'],ground_truth_source=textsource(refs),ground_truth_refs=refs,difficulty='hard',test_rationale=rationale,evaluation_kind=kind,semantic_pass_criteria=['输出为待审核结果，不宣称已发送邮件或执行退款换货；保留引用。'],**kw)
 M.append(d);return d
for row,emotion,score in [(59,'ANGRY','high'),(35,'FRUSTRATED','medium'),(41,'NORMAL','low')]:
 d=merchant('emotion_detection',row,[tsrc(row)],'独立人工标签：暴怒/挫败/平静；分析台强度和回复trace同时核对，不把关键词规则输出当标准答案。','emotion',gold_band=score);d['expected_emotion']=emotion
for row,tag in [(35,'RC1'),(42,'RC2'),(39,'RC4')]:
 d=merchant('root_cause_attribution',row,[tsrc(row)]+(osrc('Anker012') if row==39 else []),'源表只能提供线索，不能凭维修丢图推断对话上下文丢失，不能凭两种故障推断政策冲突；过保久不等于过保临界。','root',target_tag=tag)
 d['expected_root_cause_tags']=[];d['expected_unproven_tags']=[tag];d['semantic_pass_criteria']+=['不能将目标RC标签展示为已证实根因；若作为候选必须显示证据缺口。']
# independent aggregation: explicit customer error labels incl Dutch/German and E codes.
def errorcodes(text):
 out=set(re.findall(r'(?<![A-Za-z0-9])E(?:B[0-9A-Z]{2}|[0-9][0-9A-Z]?)(?=:)',text))
 for match in re.finditer(r'(?:Problem Code|Probleemcode|Fehlercode|错误码)\s*[:：]\s*(\d{4,8})',text,re.I):
  if not out or len(match[1])<=4:out.add(match[1])
 return sorted(out)
codes={r:errorcodes(str(v[2])) for r,v in T.items()}
def buckets(key):
 groups=defaultdict(list)
 for r,v in T.items():
  for label in (codes[r] or ['未提供']) if key=='codes' else [v[0] if key=='product_line' else v[6]]:groups[label].append(r)
 total=sum(map(len,groups.values()));cum=0;out=[]
 for label,rows in sorted(groups.items(),key=lambda kv:(-len(kv[1]),kv[0])):
  cum+=len(rows);out.append(dict(label=label,count=len(rows),rows=rows,share=100*len(rows)/total,cumulative=100*cum/total))
 return dict(key=key,total=total,buckets=out)
for key in ['product_line','codes','scenario']:
 merchant('pareto_aggregation',None,[src('客诉工单信息',2,'A2:G64')],'从源表独立计数；产品线不是产品名；错误码按每工单每唯一代码计一次；同条有E类用户错误码时优先该码，不重复计内部长Problem Code；缺失单列。','aggregation',dimension=key,expected_aggregation=buckets(key))
rank=[b for b in buckets('codes')['buckets'] if b['label']!='未提供'][:3]
for bucket in rank:
 code=bucket['label'];row=bucket['rows'][0];pn=str(T[row][4]).strip()[:5]
 refs=[src('eufy Robovacs Q&A',n,f'D{n}:I{n}') for n,v in Q.items() if pn in str(v[8]).split(';') and re.search(r'(?<!\w)'+re.escape(code)+r'(?!\w)',str(v[3])+' '+str(v[4])) and v[6]=='Published' and v[7]=='Visible']
 merchant('grounded_recommendation',row,[tsrc(row)]+refs,'TOP错误码建议必须关联同PN公开知识；查无则标记知识缺口，不挂不相关ID凑覆盖率。','recommendation',target_code=code,expected_knowledge_ids=[f'r-{r["excel_row"]}' for r in refs],knowledge_gap_expected=not refs)
for key in ['scenario','codes']:
 bucket=next(b for b in buckets(key)['buckets'] if b['label']!='未提供')
 merchant('drilldown',None,[src('客诉工单信息',2,'A2:G64')],'点击目标柱应展示与源表集合完全相同的工单，不多不少；接口集合和浏览器点击分别验收。','drilldown',dimension=key,selected_label=bucket['label'],expected_ticket_rows=bucket['rows'])
for row,oid,state in [(47,'Anker013','VALID'),(52,'Anker014','EXPIRED'),(49,None,'UNKNOWN')]:
 d=merchant('action_eligibility',row,[tsrc(row)]+(osrc(oid) if oid else []),'比较真实质保截止日；缺渠道与执行器时即使在保也不能批准退款换货。','eligibility',as_of_date='2026-10-16');d['expected_case_state']['warranty']=state;d['expected_case_state']['channel']='INSUFFICIENT_INFO'
for tone,row in [('formal',30),('empathetic',45)]:
 merchant('reply_tone',row,[tsrc(row)]+(osrc('Anker011') if row==30 else []),'语气改写须保持订单、SKU、已尝试步骤和事实不变，不得增加承诺。','tone',requested_tone=tone)
merchant('weekly_report',None,[src('客诉工单信息',2,'A2:G64'),src('订单信息',2,'A2:N25')],'输出全量快照并明确多数工单无日期；部分邮件有Submit Date但不能据此冒充完整周报。TOP3产品线不得用产品名替代。','weekly',expected_top_codes=rank,expected_top_product_lines=buckets('product_line')['buckets'][:3],expected_period_scope='SNAPSHOT_NOT_COMPLETE_WEEK',boundary_warning='仅能对有明确投诉日期且匹配SKU的工单核对边界；无日期不能推断。')
# one additional boundary for merchant input validation
merchant('oversized_email',longrow,[tsrc(longrow)],'以源表最长邮件原文重复构造超过20000字输入，期望拒绝而非截断后生成错误草稿。','oversized',input_transform={'operation':'repeat','times':20001//len(T[longrow][2])+1},fixture_type='synthetic_length_boundary',expected_http_status=400)
refs=[{'name':'RAGAS','url':'https://github.com/vibrantlabsai/ragas/blob/main/docs/concepts/metrics/available_metrics/faithfulness.md','use':'逐条事实的证据支持率，不把字面命中当忠实度。'},{'name':'tau-bench','url':'https://arxiv.org/abs/2406.12045','use':'工具状态与动作约束、多轮任务完成，以及k次全部成功的pass^k。'},{'name':'DeepEval','url':'https://deepeval.com/docs/evaluation-multiturn-test-cases','use':'保留turns、工具结果、检索证据，结构化用例执行。'},{'name':'MT-Bench','url':'https://arxiv.org/abs/2306.05685','use':'多轮一致性和裁判偏差提醒；人工复核语义评分。'}]
metrics=[]
def metric(ident,name,cn,formula,target,ids,method):metrics.append(dict(id=ident,name=name,name_cn=cn,formula=formula,target=target,test_cases=ids,measurement=method,target_basis='本项目拟定验收门槛，不是评测框架规定的行业标准'))
def ids(side,cats):return [d['id'] for d in side if d['category'] in cats]
metric('M_USER_1','Order Query Accuracy','订单查询准确率','正确订单且字段完整用例数 / 订单查询用例数','≥95%',ids(U,['order_query','split_shipping','missing_fields']),'比较渲染卡片与源表字段，空值须未提供；每条字段均通过方算该例通过。')
metric('M_USER_2','Entity Extraction F1','实体抽取F1','2TP/(2TP+FP+FN)','≥0.90',[d['id'] for d in U],'只对expected_entities有标注字段计分；规范化大小写与产品别名，但不能混淆SKU/PN/订单。')
metric('M_USER_3','Hallucination Rate','幻觉率','至少一条无证据事实的回答数 / 已完成逐事实审核的回答数','≤2%',[d['id'] for d in U],'人工或独立裁判逐事实核对；未审核单列，不用禁止词零命中冒充零幻觉。35条中1次已超过2%。')
metric('M_USER_4','Faithfulness','事实忠实度','证据支持的原子事实数 / 所有可核查原子事实数','≥0.98',[d['id'] for d in U],'RAGAS式分解与蕴含审核，引用存在不等于支持；无事实回答记NA。')
metric('M_USER_5','Multiturn Consistency','多轮一致性','全部轮次目标和状态检查通过的对话数 / 已评估多轮对话数','≥90%', [d['id'] for d in U if d.get('turns') or d.get('setup_turns')],'包含话题切换、同名消歧和SKU选择；整个轨迹判定。')
metric('M_USER_6','Pass^3','三次稳定成功率','连续3次均成功的任务数 / 重复执行任务总数','≥85%',[d['id'] for d in U],'每次新会话，k=3，全部成功才计入；不可用至少成功一次的pass@3代替。')
metric('M_USER_7','Language Compliance','输入语言遵循率','回应语言正确且语义相关的用例数 / 多语言用例数','100%',ids(U,['multilingual','mixed_language']),'人工核对nl/fr/de，语言下拉选en不能算已支持荷法德。')
metric('M_USER_8','Source Precision','知识引用准确率','匹配PN与问题并支持建议的引用数 / 全部知识引用数','100%',ids(U,['error_troubleshooting']),'验证ID对应原始Excel行、公开状态、PN、具体步骤。')
metric('M_MERCHANT_1','Emotion Classification Accuracy','情绪分类准确率','强度分层正确用例数 / 已标注情绪用例数','≥85%',ids(M,['emotion_detection']),'high=7–10, medium=4–6, low=0–3；三例样本仅烟测，不能估计总体85%。')
metric('M_MERCHANT_2','Pareto Aggregation Accuracy','帕累托聚合准确率','标签、计数、成员集合、占比、累计占比均正确的桶数 / 全部预期桶数','100%',ids(M,['pareto_aggregation']),'计数和成员集合精确；比例容差1e-6；缺少产品线图判失败。')
metric('M_MERCHANT_3','Action Eligibility Accuracy','动作授权判定准确率','状态与禁止动作均正确的用例数 / 授权用例总数','≥95%',ids(M,['action_eligibility']),'状态UNKNOWN不同于EXPIRED；名单匹配不等于身份核验；无执行器不得实际退款。')
metric('M_MERCHANT_4','Knowledge Grounding Rate','知识溯源率','有同PN支持知识ID的可回答建议数 / 有可用知识的建议数','100%',ids(M,['grounded_recommendation']),'无适配知识必须明确缺口，单独计缺口诚实率；不可强行绑定无关ID。')
metric('M_MERCHANT_5','Attribution Restraint','归因克制率','未把未证实RC标签当结论的例数 / 归因例数','100%',ids(M,['root_cause_attribution']),'根因无标注，只评是否承认证据不足，不以模式匹配当因果证明。')
metric('M_MERCHANT_6','Drilldown Accuracy','下钻准确率','返回行号集合精确一致的点击次数 / 下钻测试次数','100%',ids(M,['drilldown']),'UI与接口分别执行；仅API通过不得声称点击交互通过。')
metric('M_MERCHANT_7','Tone and Fact Preservation','语气与事实保真率','目标文风符合且事实不变的草稿数 / 改写草稿数','100%',ids(M,['reply_tone']),'盲审语气并逐字段对比，至少保留原已尝试信息。')
metric('M_MERCHANT_8','Weekly Report Completeness','周报准确完整率','正确完成的报告验收项 / 必需项总数','100%',ids(M,['weekly_report']),'TOP3错误码、产品线、范围声明、边界预警和引用各一项，不虚构时间序列。')
metric('M_FCR','First Contact Resolution','一次联系解决率','单次联系内解决且7天内同问题未重开的工单数 / 可观察完整7天的已接入工单数','先建立基线，目标提升需实验确认',[d['id'] for d in U],'现有源表无结案/重开轨迹，不能计算生产FCR；Demo解决率只能叫任务完成率。')
metric('M_LATENCY','Response Latency','响应时延','所有完成调用的首进度和最终答案耗时P50/P95','首进度P95≤1秒；最终答案P95≤15秒',[d['id'] for d in U],'使用单调时钟；超时计失败并单列，不能删除慢样本；固定延迟动画不算真实响应。')
suite={'metadata':{'schema_version':'1.0','source_workbook':'黑客松智能服务赛题资料.xlsx','reference_date':'2026-10-16','actual_counts':{'complaints':len(T),'unique_order_numbers':len(O),'order_item_rows':sum(map(len,O.values())),'robovac_qa':len(S['eufy Robovacs Q&A'])-1,'breast_pump_qa':len(S['eufy Breast Pump Q&A'])-1,'dealers':len(S['经销商信息'])-1},'audit_notes':['用户描述62工单/23订单与文件不符；按63工单、16订单号、24明细构造。','原文没有FURIOUS字样的三封邮件，使用真实极端不满原文，禁止补造。','无效订单、重复长邮件、假定as_of_date明确为测试夹具，不是源表事实。','质保截止日可计算日期状态，但不是退换货政策授权；政策缺失需人工确认。','RC1/RC2没有可证实根因标签，采用负向归因测试。','输入fixture_type为source_derived_question时是基于事实改写的问题，不伪装原始邮件。'],'source_workbook_sha256':hashlib.sha256((ROOT.parent.parent/'黑客松智能服务赛题资料.xlsx').read_bytes()).hexdigest(),'source_snapshot_sha256':hashlib.sha256((ROOT/'source-snapshot.json').read_bytes()).hexdigest(),'framework_references':refs},'user_test_cases':U,'merchant_test_cases':M,'metrics':metrics,'codex_evaluation_instructions':{'execution':['先校验source_snapshot_sha256与源文件版本；源表行号包含表头。','每个用例创建独立session_id；setup_turns先执行，turns按顺序执行；保存每轮响应、引用、trace与延迟。','用户端POST /api/chat；商家草稿POST /api/mail/stream读取NDJSON最后result；分析GET /api/analytics；周报GET /api/analytics/report/weekly。','使用evaluation/run_suite.py执行离线完整规则基线（禁用LLM）与--live选定样本的真实HTTP评估，结果分开保存；离线成功不代表LLM通过。','需要特殊as_of_date时只在隔离测试进程替换app.date，不能修改主机时钟；live环境不支持日期注入则标为BLOCKED。','语气改写在已有草稿上POST /api/mail/rewrite，action=versions；需人工检查正式/共情两个版本，不真实发信。'],'pass_fail':['自动硬断言全部通过且语义评审全部通过，才标PASS；任一失败标FAIL。','只通过自动字段断言而语义未审标REVIEW_REQUIRED；缺少接口/日期夹具标BLOCKED或NOT_RUN，绝不计入通过。','must_contain为必要内容提示；译文可语义等价。禁止词需检查否定上下文，不能因“无法退款”误判执行成功。','source_id存在不足以证明忠实度，必须确认同PN、正确错误码及原文支撑。','多轮任务按完整轨迹判；合法源字段含空值时不得从相邻商品补值。','不得按当前Demo错误行为改写ground truth；发现失败先记缺陷，不自动修改业务代码。'],'visualization':{'radar_dimensions':['订单与物流准确性','知识与引用忠实度','多轮与语言理解','情绪与回复质量','动作授权安全性','聚合与报告正确性'],'normalization':'每轴=对应已审核通过项/对应已执行项*100；同时显示覆盖率；未审核维度留空而不是0或100。','companions':['用例结果表含PASS/FAIL/REVIEW_REQUIRED/BLOCKED/NOT_RUN','类别通过率热图和缺陷列表','延迟P50/P95与模型调用次数','样本量和95%置信区间；小样本不可声称总体达到行业水平']}}}
for d in U:
 if 'fixture_type_override' in d:d['fixture_type']=d.pop('fixture_type_override')
assert len(U)>=30 and len(M)>=20
allids={d['id'] for d in U+M};assert all(set(x['test_cases'])<=allids for x in metrics)
(ROOT/'ontocare-test-suite.json').write_text(json.dumps(suite,ensure_ascii=False,indent=2))
print('Generated',len(U),'user,',len(M),'merchant,',len(metrics),'metrics; top codes:',[(b['label'],b['count']) for b in rank])
