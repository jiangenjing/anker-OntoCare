// All values come from archived result files embedded by the report builder.
function renderRecordedResults(){
 const h=DATA.evaluation_history;
 const metric=id=>h.metrics.find(m=>m.mode==='online'&&m.id===id);
 const localTime=s=>s?new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（北京时间）':'未记录运行时间';
 const coreResult=run=>run.summary.online.pass_k.find(p=>p.k===1);
 const base=coreResult(h.baseline),fixed=coreResult(h.repair),all=h.repair.summary.online,p50=metric('latency_p50');
 $('resultsImprovement').textContent='结合 Persona 多轮红蓝对抗、规则硬断言及 LLM-as-Judge，建立失败轨迹定位、知识／规则修订和回归验证流程；'+base.eligible+' 项核心任务线上硬断言通过率由历史基线 '+(base.rate*100).toFixed(2)+'%（'+base.passed+'/'+base.eligible+'）提升至修复后单轮复测 '+(fixed.rate*100).toFixed(2)+'%（'+fixed.passed+'/'+fixed.eligible+'），提高 '+((fixed.rate-base.rate)*100).toFixed(2)+' 个百分点，保留失败记录与复测证据。';
 const card=(name,value,note,emphasis=false)=>'<article class="results-stat'+(emphasis?' emphasis':'')+'"><span>'+esc(name)+'</span><b>'+esc(value)+'</b><small>'+esc(note)+'</small></article>';
 $('resultsStats').innerHTML=card('历史核心硬断言',pct(base.rate),base.passed+'/'+base.eligible+' · 在线首轮')+card('修复后核心硬断言',pct(fixed.rate),fixed.passed+'/'+fixed.eligible+' · 单次复测',true)+card('修复后全量用例',all.passed+'/'+all.trials,'在线与离线各一轮 · 保留 U060 失败')+card('历史完整响应 P50',secs(p50.value),p50.denominator+' 次非注入请求 · 非首字时延');
 $('resultsComparison').innerHTML=[['历史基线',base,h.baseline,false],['后续修复复测',fixed,h.repair,true]].map(([label,r,run,emphasis])=>'<div class="results-bar-row"><div class="results-bar-label"><b>'+label+'</b><span>'+pct(r.rate)+' · '+r.passed+'/'+r.eligible+'</span></div><div class="results-bar"><span class="'+(emphasis?'measured':'')+'" style="width:'+(r.rate*100)+'%"></span></div><p class="caption">'+localTime(run.generated_at)+' · 代码 '+esc(run.config.code_hash.slice(0,12))+'</p></div>').join('');
 const historical=h.baseline.summary;
 $('resultsCoverage').innerHTML='<p><b>110</b> 条用例 · <b>74</b> 个核心任务 · <b>'+DATA.personas.length+'</b> 类 Persona</p>'+table(['历史模式','执行记录','pass³','pass⁸'],['online','offline'].map(mode=>[mode==='online'?'在线模型':'离线规则',String(historical[mode].trials),...historical[mode].pass_k.filter(p=>p.k===3||p.k===8).map(p=>pct(p.rate)+' <span class="muted">('+p.passed+'/'+p.eligible+')</span>')]))+'<p class="caption">修复后 pass³ / pass⁸：<b>未测</b>。历史重复记录不能证明多次语义回答均正确。</p>';
 $('resultsSemantic').innerHTML=[['faithfulness','主张获得来源支持','主张级；越高越好'],['joint','硬断言＋裁判联合通过','轨迹级；越高越好'],['unsupported_answer','含不支持主张的轨迹','轨迹级；越低越好']].map(([id,label,note])=>{const m=metric(id);return '<div class="results-measure"><span>'+label+'</span><b>'+pct(m.value)+'</b><small>'+m.numerator+'/'+m.denominator+' · '+note+'</small></div>'}).join('');
 const button=(index,version,row)=>'<button data-result-trace="'+index+'" data-result-version="'+version+'">'+(version==='repair'?'修复后':'历史')+' · '+(row.status==='PASS'?'通过':'失败')+' · Trace</button>';
 $('resultsCases').innerHTML=table(['用例','问题','历史在线首轮','修复后单次'],h.examples.map((e,i)=>[esc(e.id),esc(e.label),button(i,'baseline',e.baseline),button(i,'repair',e.repair)]));
 $('resultsProbe').textContent=h.timeout_probe.id+'：'+h.timeout_probe.status+'。另选未缓存问题，超时注入命中后验证降级；U060 仍记 FAIL，未修改原结果。';
 $('resultsRedblue').innerHTML=table(['Prompt 版本','北京时间','实际轮数','结果','证据'],h.redblue.map((r,i)=>[esc(r.prompt_version),esc(localTime(r.created_at)),String(r.trace.turns.length),pill(r.trace.final_verdict.status),'<button data-result-redblue="'+i+'">查看逐轮对抗</button>']));
 $('resultsEarlier').innerHTML='<h3 style="margin-top:16px">早期 57 条双端套件</h3><p>'+Object.entries(h.early.counts).map(([k,v])=>esc(k)+' '+v).join(' · ')+'</p><p class="caption">早期套件与后续 Benchmark 的同名用例编号不共享含义。该记录为全量运行叠加局部修复复测的复核版，U028 保留 BLOCKED，不是同一版本 57 条全部通过。</p>';
 const value=m=>m.value==null?'未测':m.unit==='ratio'?pct(m.value):m.unit==='ms'?secs(m.value):m.unit==='score_1_5'?m.value.toFixed(2)+'/5':String(m.value);
 $('resultsAllMetrics').innerHTML='<h3>历史在线指标明细</h3>'+table(['指标','结果','分母与范围'],h.metrics.filter(m=>m.mode==='online').map(m=>[esc(m.name),esc(value(m)),esc((m.denominator==null?'':m.denominator+'；')+(m.scope||m.reason||''))]));
 $('resultsSources').innerHTML='<p class="caption">生成时读取保存的结果并内嵌，不发起新评测。无时间字段的来源保持未记录；哈希用于核对文件版本。</p>'+h.sources.map(s=>'<div class="results-source">'+esc(s.path)+'\n'+esc(localTime(s.generated_at))+'\nSHA256 '+esc(s.sha256)+'</div>').join('');
 renderEvaluationHighlights();
}

function renderEvaluationHighlights(){
 const features=[
  ['真实业务金标准','5 张源表关联出题。63 条工单、16 个订单号、875 条知识；首封邮件保留原文，来源可核对。','查看原始工单','sources'],
  ['Persona 多轮对抗','8 类用户画像驱动追问，覆盖急躁、多语言、技术型与安全敏感用户；情绪变化由代码控制。','查看画像与对抗实测','personas'],
  ['三层联合验收','先核对订单、SKU 与引用，再由模型评估证据与语气，最后检查本地会话终态和动作边界。','查看判定机制','judge'],
  ['重复与扰动验证','核心任务重复运行，按前 k 次全部通过计算 passᵏ；另有同义改写、语序调整、噪音输入探针。','查看重复记录与扰动','reliability'],
  ['故障注入验证兜底','注入超时、429 限流、响应截断和字段漂移，检查是否有有效回答、引用及明确降级原因。','查看 4 类故障证据','chaos'],
  ['Bad Case 回归闭环','按失败断言定位问题，人工修复知识或规则，再保留版本重新验证；已修复与仍失败分别展示。','查看修复前后证据','repair'],
 ];
 $('methodCards').innerHTML=features.map(([title,body,label,key],i)=>'<article class="method-card"><span class="method-number">0'+(i+1)+'</span><h3>'+title+'</h3><p>'+body+'</p><button data-method="'+key+'">'+label+'</button></article>').join('');
}

function showEvaluationMethod(key){
 const h=DATA.evaluation_history;
 const boundary=text=>'<p class="method-boundary">'+text+'</p>';
 if(key==='sources'){$('archSources').click();return}
 if(key==='personas'){
  const rows=DATA.personas.map(p=>{
   const c=DATA.cases.find(c=>c.persona_id===p.id&&c.persona_probe);
   return [esc(p.id+' · '+p.name),esc(p.source_sheet+' · 第 '+p.source_excel_row+' 行'),c?evidence(c.id,'原信与历史 Trace'):'未记录'];
  });
  show('Persona：原信出题，受控追问',table(['画像','原文来源','证据'],rows)+'<p>首轮使用源表原文；新动态模式支持模型追问，情绪值、耐心与最多 8 轮上限由代码控制。后续追问是模拟内容，不当作真实客户邮件。</p>'+h.redblue.map((r,i)=>'<p>'+esc(r.prompt_version)+' · '+r.trace.turns.length+' 轮 · '+pill(r.trace.final_verdict.status)+' <button data-result-redblue="'+i+'">查看动态对抗 Trace</button></p>').join('')+boundary('已记录的三次在线动态实验均为 U093 同一场景，每版本一次；8 类 Persona 不代表 8 个在线场景已全部通过。'));return;
 }
 if(key==='judge'){
  show('联合验收：事实、表达与业务状态',table(['层级','检查什么','真实证据'],[
   ['规则断言','订单字段、SKU、引用来源、禁止承诺与未核验地址',evidence('A003','地址披露失败记录')],
   ['LLM Judge','基于来源逐项判断主张支持、语气与动作合法性','<button data-result-redblue="0">查看语义裁判未通过案例</button>'],
   ['本地终态','质保等会话状态、只读订单不变、交接字段完整性',evidence('U062','查看交接状态缺口')]
  ])+boundary('借鉴 τ-bench 的终态与 passᵏ、RAGAS 的忠实度思想；不是这些框架的官方基准成绩。模型裁判未经人工校准，真实退款、换货执行与 7 日 FCR 未测。'));return;
 }
 if(key==='reliability'){
  const probes=DATA.cases.filter(c=>c.perturbation_type);
  show('重复稳定性：不是把单次通过率乘方','<div class="method-formula">passᵏ = 前 k 次全部硬断言通过的任务数 / 具备 k 次记录的任务数</div>'+table(['历史模式','pass¹','pass³','pass⁸'],['online','offline'].map(m=>[m==='online'?'在线模型':'离线规则',...h.baseline.summary[m].pass_k.map(p=>pct(p.rate)+' ('+p.passed+'/'+p.eligible+')')]))+'<h3 style="margin-top:16px">已配置的扰动探针</h3>'+table(['探针','类型','证据'],probes.map(c=>[esc(c.id),esc(c.perturbation_type),evidence(c.id)]))+boundary('历史核心任务各重复 8 次，只统计硬断言。后续修复仅复测一轮，不能据此计算新的 pass³/pass⁸，也没有证明重复语义质量。'));return;
 }
 if(key==='chaos'){
  show('混沌探针：故障后能否诚实降级',table(['注入类型','检查重点','历史记录'],[
   ['API 超时','回答仍可用、保留引用、记录降级原因',evidence('U051')],
   ['429 限流','有界兜底，不冒充模型成功',evidence('U052')],
   ['响应截断','不将不完整结果当成完整回答',evidence('U053')],
   ['接口字段漂移','返回可解释错误，不崩溃或编造订单字段',evidence('U054')]
  ])+'<p>修复后的 U060 仍因超时注入未触发而失败；补充探针 U060-R1 单独验证，未覆盖原失败。</p>'+boundary('这些是测试环境注入，不代表已验证真实生产故障和高并发 SLA。文档中的“≥85%”等阈值是目标，不是成绩。'));return;
 }
 if(key==='repair'){
  show('Bad Case：发现 → 人工修复 → 回归',table(['问题','历史基线','修复后单次'],h.examples.map((e,i)=>[esc(e.id+' · '+e.label),'<button data-result-trace="'+i+'" data-result-version="baseline">'+pill(e.baseline.status)+' 查看 Trace</button>','<button data-result-trace="'+i+'" data-result-version="repair">'+pill(e.repair.status)+' 查看 Trace</button>']))+boundary('知识、规则与代码修复需要人工审核；未实现自动修改向量权重或无人审核写回政策。修复备注不改变历史成绩。'));
 }
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-method]');if(b)showEvaluationMethod(b.dataset.method)});
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-result-trace],[data-result-redblue]');if(!b)return;
 const h=DATA.evaluation_history;
 if(b.dataset.resultRedblue!==undefined){const r=h.redblue[Number(b.dataset.resultRedblue)];showTrace(r.trace,'archived-'+r.run_id);return}
 const example=h.examples[Number(b.dataset.resultTrace)],version=b.dataset.resultVersion;
 const row=example[version],run=h[version],trace=recordTrace(byId[example.id],row);
 trace.provenance=(version==='repair'?'修复复测 · 单次硬断言':'历史基线 · 首轮')+' · '+run.generated_at;
 showTrace(trace,version+'-'+run.config.code_hash);
});
