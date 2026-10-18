"""Render measured results; semantic judgments must match the exact response hash."""
from pathlib import Path
import json,html,hashlib
R=Path(__file__).parent
load=lambda name:json.loads((R/name).read_text())
before=load('baseline-before-fixes/results-offline.json');after=load('results-offline.json');live=load('results-live.json')
notes=load('review-notes.json') if (R/'review-notes.json').exists() else {}
for r in live['results']:
 note=notes.get(r['id'],{})
 digest=hashlib.sha256(json.dumps(r.get('response'),ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 r['automated_status']=r['status']
 if note.get('response_sha256')==digest:
  r['semantic_review']=note
  r['status']='FAIL' if not r.get('hard_checks_passed') else note['verdict']
 else:r['semantic_review']={'status':'NOT_REVIEWED','reason':'本次输出尚未审核，不沿用历史判定'}
live['counts']={s:sum(r['status']==s for r in live['results']) for s in ['PASS','FAIL','REVIEW_REQUIRED','BLOCKED','ERROR']}
(R/'results-live-reviewed.json').write_text(json.dumps(live,ensure_ascii=False,indent=2))
E=lambda v:html.escape(str(v))
old={r['id']:r for r in before['results']}
rows=''
for r in after['results']:
 info='；'.join(c['check'] for c in r.get('checks',[]) if not c['passed'])
 if not info:info='硬断言通过；完整语义不由此推断' if r.get('hard_checks_passed') else (r.get('response') or {}).get('reason','待检查')
 rows+=f"<tr><td>{E(r['id'])}</td><td>{E(r.get('category'))}</td><td>{E(old.get(r['id'],{}).get('status'))}</td><td>{E(r['status'])}</td><td>{E(info)}</td></tr>"
reviews=''
for r in live['results']:
 d=r.get('response') or {};trace=d.get('trace',{})
 text=d.get('reply',d.get('draft',d.get('result',{}).get('text','')))
 reviews+=f"<tr><td>{E(r['id'])}</td><td>{E(r['status'])}</td><td>{r.get('seconds',0):.1f}s</td><td>{E(trace.get('model_status','改写接口'))}<br>{E(trace.get('model_validation',{}))}</td><td>{E(r['semantic_review'].get('reason',''))}<details><summary>实际回复</summary><pre>{E(text)}</pre></details></td></tr>"
c=live['counts'];hard=sum(r.get('hard_checks_passed',False) for r in after['results'])
page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>安小克 · 修复后测评报告</title><style>body{{font:14px/1.7 -apple-system,"PingFang SC",Arial;max-width:1200px;margin:32px auto;padding:0 20px;background:#fafafa;color:#111}}section{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:22px;margin:18px 0}}h1{{font-size:28px}}.metrics{{display:flex;gap:28px;flex-wrap:wrap}}.metric b{{display:block;font-size:32px}}.note{{color:#666}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #eee;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;max-width:700px;font:inherit}}input{{padding:10px;border:1px solid #ddd;width:90%}}a{{color:#111}}.good{{color:#008447}}</style><h1>安小克 / Anka · 测评修复复验</h1><p>同一份源表 · 同一套57条金标准 · 用户端 + 商家端</p><section><div class="metrics"><div class="metric"><span>离线硬断言失败</span><b>{before['counts']['FAIL']} → {after['counts']['FAIL']}</b></div><div class="metric"><span>代码回归测试</span><b>127 / 127</b></div><div class="metric"><span>真实接口全量执行</span><b>{len(live['results'])} 条</b></div></div><p>完整离线57条：{hard}条硬断言通过；2条语气改写在离线模式不调用模型，由真实接口补测。真实接口语义审核：{c['PASS']}通过 / {c['FAIL']}失败 / {c['REVIEW_REQUIRED']}待审核；U028指定参考日用例线上不可注入，已在离线通过。全量运行后，5条涉及最终约束的用例另行复测并合并，历史原始结果均保留。</p><p class="note">硬断言覆盖状态、来源ID、源表字段和统计集合，不等于完整回答质量。语义审核为本次助手按预定规则审阅，非独立人类双盲审核；不宣称全量真实模型通过率或行业认证。模型外部服务仍可能超时，页面如实显示回退。</p></section><section><h2>这次修了什么</h2><p>当前产品选择优先；S1 Pro品类澄清；五语言回复；两端一致的情绪规则；经销商国家与名称核验；使用问题检索；物流冲突与已尝试步骤保留；安全停用兜底；错误码提取、产品线统计、下钻和周报；邮件全正文语气改写及字段保护。</p><p>浏览器已检查：3212下钻为第19、28行；周报TOP错误码为3212=2、2111=1、2310=1。产品线只有源表中的Anker eufy，不补造三条。</p><p class="note">客户归属、实际退款/换货/发信均未自动执行。投诉时间未完整结构化，周报仍是全量快照，不是实际周变化。</p></section><section><h2>真实模型回复与审核</h2><table><tr><th>编号</th><th>结果</th><th>耗时</th><th>模型状态</th><th>审核说明</th></tr>{reviews}</table></section><section><h2>全量离线前后对照</h2><input id="q" placeholder="搜索用例编号、FAIL、场景"><table id="results"><tr><th>编号</th><th>场景</th><th>修复前</th><th>修复后</th><th>说明</th></tr>{rows}</table></section><section><h2>测评资料</h2><p><a href="ontocare-test-suite.json">完整测评集</a> · <a href="results-live-reviewed.json">真实接口响应和审核</a> · <a href="results-offline.json">完整离线原始结果</a> · <a href="OntoCare 测评修复计划与执行记录.md">Plan / Action 与验证口径</a> · <a href="baseline-before-fixes/测评报告.html">修复前报告</a></p><p>参考方法：<a href="https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/">RAGAS忠实度</a>、<a href="https://arxiv.org/abs/2406.12045">τ-bench多轮任务</a>。本次使用项目自有判定器，没有运行这些框架的官方评分器。</p></section><script>document.getElementById('q').oninput=e=>{{for(const r of document.querySelectorAll('#results tr:not(:first-child)'))r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase())}}</script></html>'''
(R/'测评报告.html').write_text(page)
print('Rendered',live['counts'])
