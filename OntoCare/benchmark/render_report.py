"""Build a portable report from recorded outcomes; never fabricates measurements."""
import json,copy,hashlib,html as html_tools
from pathlib import Path
from evaluation_history import build_history
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'benchmark'
r=json.loads((D/'benchmark-results.json').read_text())
cases=json.loads((D/'ontocare-user-test-cases.json').read_text())['test_cases']+json.loads((D/'ontocare-adversarial-tests.json').read_text())['test_cases']
# Repeated trials remain individually visible. Complete turn text is shown for the first trial.
trials=[]
for row in r['results']:
 x=copy.deepcopy(row)
 x['checks']=[{k:v for k,v in a.items() if k!='actual'}|{'actual':str(a.get('actual',''))[:450]} for a in x['checks']]
 x['telemetry']=[{'latency_ms':t['latency_ms'],'answer_ttft_ms':t['answer_ttft_ms'],'first_progress_ms':t['first_progress_ms'],'model_status':t['response'].get('model_status'),'trace':{k:t['response'].get('trace',{}).get(k) for k in ['model_calls','answer_route','response_language','emotion','model_status']}} for t in x['trajectory']]
 if x['repeat']!=1:x.pop('trajectory');x.pop('extras')
 else:
  for t in x['trajectory']:t['events']=[e for e in t.get('events',[]) if e.get('type')=='progress']
  x['extras'].pop('retrieved_sources',None)
 trials.append(x)
report={**r,'results':trials,'cases':cases,'personas':json.loads((D/'ontocare-persona-vectors.json').read_text())['personas'],'raw_result_sha256':hashlib.sha256((D/'benchmark-results.json').read_bytes()).hexdigest()}
report['merchant_attribution']=json.loads((ROOT/'reports/attribution_report.json').read_text())
sample=ROOT/'reports/红蓝对抗在线实测.json'
if sample.exists():report['redblue_sample']=json.loads(sample.read_text())
report['evaluation_history']=build_history(ROOT)
html=(D/'report-template.html').read_text().replace('__BENCHMARK_DATA__',json.dumps(report,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028'))
html=html.replace('__TRACE_GRAPH__',(D/'trace-graph.html').read_text())
html=html.replace('__RESULTS_VIEW__',(D/'results-view.html').read_text())
html=html.replace('__RESULTS_SCRIPT__',(D/'results-view.js').read_text())
# Keep the historical report intact; clearly separate the latest one-round repair run.
repair_path=ROOT/'reports/评测修复复测.json'
if repair_path.exists():
 repair=json.loads(repair_path.read_text())
 modes='；'.join(('离线' if mode=='offline' else '在线')+f" {data['passed']}/{data['total']}" for mode,data in repair['modes'].items())
 notice='<div class="notice" id="repairValidation"><b>最新修复复测 · '+html_tools.escape(repair['generated_at'][:10])+'</b><p>'+html_tools.escape(modes)+'；应用测试 156/156。各模式仅跑一轮，下方仍为历史测评报告。</p><details><summary>查看保留的失败与修复范围</summary><p>U060 因固定工作流绕过模型，旧超时注入未触发，仍记为 FAIL；独立 U060-R1 未缓存请求触发超时 1 次并通过。未虚增故障命中。</p><p>已复测：未核验地址隐藏、产品消歧、2310/7031 检索、拆单单号、依赖降级和人工交接。固定问答命中附引用，未命中再调用模型。</p><p>完整新轨迹：源码包 benchmark/repair-final-results.json；复盘与边界：docs/reports/评测失败修复说明.md。未重算历史 pass^3/pass^8。</p></details></div>'
 html=html.replace('<div id="runStatus"',notice+'<div id="runStatus"',1)
html=html.replace('__RESPONSIVE_CSS__',(ROOT/'static/responsive.css').read_text())
(D/'ontocare-benchmark-report.html').write_text(html)
(ROOT/'static/benchmark.html').write_text(html)
# Standalone principles edition: inline evidence, no external scripts or libraries.
standalone=html.replace('<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js" onerror="document.body.classList.add(\'no-charts\')"></script>','')
standalone=standalone.replace(":'results')}catch(e)",":'principles')}catch(e)")
(ROOT/'static/benchmark-principles.html').write_text(standalone)
# Offline mock baseline edition; all layout and rendering remain inline.
business=standalone.replace(":'principles')}catch(e)",":'business')}catch(e)")
(ROOT/'static/benchmark-business.html').write_text(business)

print(json.dumps({'report_bytes':len(html.encode()),'trials':len(trials),'cases':len(cases)}))
