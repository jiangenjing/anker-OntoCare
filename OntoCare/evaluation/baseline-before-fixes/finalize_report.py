from pathlib import Path
import json,html,math,shutil
ROOT=Path(__file__).parent
suite=json.loads((ROOT/'ontocare-test-suite.json').read_text())
offline=json.loads((ROOT/'results-offline.json').read_text());live=json.loads((ROOT/'results-live.json').read_text())
judgments={
'U001':('PASS','卡片正确显示Anker003、T2351V11-F、257.5及原表物流；没有冒充实时查询。'),
'U007':('FAIL','回复未明确复述label created与Delivered冲突，只展示快照并再次索取已在原文中的单号；模型INVALID_RESPONSE退回兜底。'),
'U013':('PASS','同PN检索r-24，回应6011并给密封圈检查，引用内容支撑步骤。'),
'U020':('FAIL','回复有共情，但trace仍为NORMAL，未达到用例要求的强烈情绪识别。'),
'U023':('FAIL','荷兰语原文明确Anker006未收到，返回中文“请告诉我具体产品型号和问题”，未答物流且语言不符合。'),
'U029':('FAIL','US及Aeroflow Breastpumps完整输入仍未命中经销商名录，反而要求型号。'),
'U034':('PASS','承接烫伤风险，要求停用并人工核查，未承诺已换货/退款或虚构诊断。'),
'U035':('PASS','完整轨迹由Anker002物流切换到T2080 EB1L，最终引用r-482并回答注水异常。'),
'M015':('FAIL','草稿未回应原文电机异响，只说补充笔记为策略、确认购买渠道，模型格式校验失败。'),
'M016':('FAIL','草稿没有回应原文充电后不能保电、使用中断电，仅给泛化审核说明，模型格式校验失败。')}
for r in live['results']:
 state,note=judgments[r['id']];r['automated_status']=r['status'];r['status']=state;r['semantic_review']={'status':'REVIEWED','method':'本次助手按预先定义rubric审阅实际回复与源表；不是独立人类双盲审核','verdict':state,'reason':note}
live['counts']={s:sum(r['status']==s for r in live['results']) for s in ['PASS','FAIL','REVIEW_REQUIRED','BLOCKED','ERROR']}
(ROOT/'results-live-reviewed.json').write_text(json.dumps(live,ensure_ascii=False,indent=2))
readme='''# OntoCare 安小克 / Anka 测评结果

本次交付36条用户端、21条商家端，共57条用例，18项指标。来源是本次上传Excel，不使用应用输出生成标准答案。每条有Excel行号、事实依据、预期、难度与自动/语义判定；未改业务实现。

## 源数据核对
63条工单、16个订单号、24条订单明细，593条扫地机Q&A、282条吸奶器Q&A、336条经销商记录。序号到23但另有无序号配件行。公开知识与当前Demo对比，Title/Content不一致数为0。
无效订单号、重复构造的超长邮件、质保参考日是明确标注的测试夹具，不冒充真实业务记录。原始最长邮件729字符；超长输入使用重复原文生成，测试上限拒绝行为。

## 已执行结果
离线完整执行57例，禁用LLM：1通过、15硬断言失败、39硬断言通过但语义待审核、2阻塞（正式/共情指定语气尚无接口）。不能将39条直接算通过。
当前运行Demo真实HTTP抽测10例，经本次助手依据源表逐例审阅：4通过、6失败。这里只是小样本验收，不是行业分数，也不代表完整57例的LLM通过率。结果详情与实际响应见results-live-reviewed.json；原始未审结果保存在results-live.json。
没有执行真实发信、退款、换货；未将API下钻集合检查声称为浏览器点击测试。没有安装或运行RAGAS、DeepEval、MT-Bench官方评分器；只借鉴其方法，不能称为框架官方认证。

## 优先缺陷
1. U012：同订单明确询问C10，产品识别仍为X10。需区分提及的型号与当前选中型号。
2. U020–U022/M001：强烈不满、脏话被判NORMAL或低强度。英文情绪词覆盖不足，回复共情不能代替情绪状态正确。
3. U029/U030：US + Aeroflow Breastpumps / best buy输入未解析成经销商查找。名录本身有记录，应补槽位抽取；命中也不能当购买凭证。
4. M008/M010/M011/M014：漏识别荷兰语Probleemcode、德语Fehlercode及E41/E53/EB03等，错误码聚合和下钻成员错误。按用户可读码优先，避免内部长Problem Code重复计数。
5. M007/M020：分析只提供产品名图，缺产品线图；周报也缺TOP产品线。不能把两者互换。
6. U023：荷兰语原文被错误兜底为中文澄清；当前对话language逻辑只区分zh/en，需完整多语言策略。
7. U036：吸奶器自定义节奏在Q&A第2行有答案，但离线流程未检索，要求提供症状。需覆盖产品使用意图。
8. U034：离线安全回复没明确停用；真实LLM抽测有补上。安全建议不应依赖模型偶然生成。
9. M018/M019：正式/共情风格选择未接入接口；现有short/standard/detailed是详略，不是语气。
10. U007/M015/M016：真实模型返回INVALID_RESPONSE后，兜底缺少针对性。应保留客户已有信息和明确诉求，记录格式失败原因。

## 测评口径
错误码金标准从原始邮件独立提取：识别英文/荷兰语/德语明确代码字段及带冒号的E类码，避免把产品E25/E28误当错误码；同工单有E类面向用户代码时不重复计内部长数字代码。每工单每唯一错误码一次，未提供单列。排序按数量降序、同频按代码字符串升序；TOP3存在同频，只用于可复现展示，不代表严重程度。
根因RC1/RC2无证实标签，测是否克制归因；没有充分来源不要求强行命中标签。周报多数工单缺投诉日期，少数含Submit Date，不可声称所有日期都没有，也不可生成完整周趋势。保修到期日包含当天仅为待业务确认的测试口径，不是官方政策。
指标阈值是本项目拟定验收目标。生产FCR缺结案/重开轨迹不可计算。pass^3需三次独立重跑，本次未执行；首进度P95、完整忠实度与六轴综合雷达未评完，均留空，不填100%。

## 复现
在源码目录执行：
- `.venv/bin/python evaluation/run_suite.py`：隔离进程、完整规则基线，不调用模型。
- `.venv/bin/python evaluation/run_suite.py --live --ids U001,U007,U013,U020,U023,U029,U034,U035,M015,M016`：请求本地5088服务，沿用已配置模型，消耗模型额度，不发信。
- 去掉--ids可运行完整真实接口测试；边界参考日期无法注入线上接口，标为BLOCKED。每例独立会话。
- 按JSON内semantic_pass_criteria进行人工复核，再更新结果。硬断言通过仅表示字段/状态符合，不等于回答完全正确。

## 参考
- RAGAS事实支持率：https://github.com/vibrantlabsai/ragas/blob/main/docs/concepts/metrics/available_metrics/faithfulness.md
- τ-bench多轮工具与pass^k：https://arxiv.org/abs/2406.12045
- DeepEval多轮测试结构：https://deepeval.com/docs/evaluation-multiturn-test-cases
- MT-Bench多轮评价与裁判偏差：https://arxiv.org/abs/2306.05685
'''
(ROOT/'安小克 - Anka 修复后复测说明.md').write_text(readme)
allcases={c['id']:c for c in suite['user_test_cases']+suite['merchant_test_cases']}
rows=''
for r in offline['results']:
 failures=[x['check'] for x in r.get('checks',[]) if not x['passed']]
 rows+=f'<tr><td>{r["id"]}</td><td>{html.escape(allcases[r["id"]]["category"])}</td><td>{r["status"]}</td><td>{html.escape("；".join(failures) or (r.get("response") or {}).get("reason", "硬断言已通过；正文语义仍待审核"))}</td></tr>'
review=''.join(f'<tr><td>{r["id"]}</td><td>{r["status"]}</td><td>{r.get("seconds",0):.2f}s</td><td>{html.escape(r["semantic_review"]["reason"])}</td></tr>' for r in live['results'])
labels=suite['codex_evaluation_instructions']['visualization']['radar_dimensions'];svg='<svg viewBox="0 0 620 390" role="img" aria-label="六维雷达模板，综合语义评分未完成，无填充得分">'
for scale in [.25,.5,.75,1]:
 pts=' '.join(f'{310+135*scale*math.cos(-math.pi/2+i*math.pi/3):.1f},{190+135*scale*math.sin(-math.pi/2+i*math.pi/3):.1f}' for i in range(6));svg+=f'<polygon points="{pts}" fill="none" stroke="#ddd"/>'
for i,label in enumerate(labels):
 a=-math.pi/2+i*math.pi/3;x=310+165*math.cos(a);y=190+165*math.sin(a);svg+=f'<text x="{x}" y="{y}" text-anchor="middle" font-size="12">{label}</text><text x="{x}" y="{y+16}" text-anchor="middle" font-size="11" fill="#777">待完整语义审核</text>'
svg+='</svg>'
page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>安小克 / Anka 测评报告</title><style>body{{font:14px/1.7 -apple-system,Arial;max-width:1120px;margin:32px auto;padding:0 20px;color:#111;background:#fafafa}}section{{background:white;border:1px solid #ddd;border-radius:8px;padding:20px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #ddd;vertical-align:top;overflow-wrap:anywhere}}svg{{max-width:620px;width:100%}}input{{padding:10px;width:90%;border:1px solid #bbb}}.note{{color:#666}}h1{{font-size:26px}}</style><h1>安小克 / Anka · 双视图测评</h1><p>57条用例 · 5张源表 · 18项指标 · 本次不修改业务代码</p><section><h2>实测结论</h2><p>离线：1通过 / 15失败 / 39语义待审核 / 2阻塞。真实接口抽测10条：4通过 / 6失败。</p><p class="note">抽测由本次助手逐例审阅，不是独立人类双盲审核；硬断言不等于完整客服质量，不能据此宣称达到行业标准。</p></section><section><h2>六维雷达</h2>{svg}<p class="note">未完成全量语义评分，雷达保留空值。避免把引用ID匹配当作100%事实忠实度。</p></section><section><h2>真实接口抽测</h2><table><tr><th>用例</th><th>结果</th><th>用例总耗时</th><th>依据</th></tr>{review}</table></section><section><h2>完整离线结果</h2><input id="q" placeholder="筛选编号、场景或FAIL"><table id="results"><tr><th>用例</th><th>场景</th><th>结果</th><th>检查说明</th></tr>{rows}</table></section><p><a href="ontocare-test-suite.json">完整JSON测评集</a> · <a href="安小克 - Anka 修复后复测说明.md">缺陷与复现说明</a></p><script>document.getElementById('q').oninput=e=>{{for(const r of document.querySelectorAll('#results tr:not(:first-child)'))r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase())}}</script></html>'''
(ROOT/'测评报告.html').write_text(page)
shutil.copy2(ROOT/'ontocare-test-suite.json',ROOT.parent.parent/'ontocare-test-suite.json')
print('Report written; reviewed live:',live['counts'])
