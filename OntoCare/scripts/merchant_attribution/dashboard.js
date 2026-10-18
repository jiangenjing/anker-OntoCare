const $=id=>document.getElementById(id),esc=v=>String(v??'未提供').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let returnFocus;
const advice=REPORT.improvement_advice,all=REPORT.tickets;
function refs(ids){return '<div class="source">'+ids.slice(0,3).map(n=>`<button data-row="${n}">工单第${n}行</button>`).join('')+(ids.length>3?`<button data-rows="${ids.join(',')}" data-label="全部依据">全部 ${ids.length} 条依据</button>`:'')+'</div>';}
function show(title,body){returnFocus=document.activeElement;$('drawerTitle').textContent=title;$('drawerBody').innerHTML=body;$('overlay').classList.add('open');$('close').focus();}
function close(){$('overlay').classList.remove('open');returnFocus?.focus();}
function mail(t){const orders=REPORT.order_snapshot.flatMap(o=>o.items).filter(i=>t.order_rows.includes(i['原文行号']));return `<div class="source-row"><h3>工单第 ${t.row} 行 · ${esc(t.product)}</h3><p class="small">PN ${esc(t.pn)} · SKU ${esc(t.sku)} · 订单 ${esc(t.order_no)}</p><div class="email">${esc(t.email)}</div><p class="small">来源：客诉工单信息表第 ${t.row} 行；${t.raw_codes?.length?'原始码 '+esc(t.raw_codes.join(' / '))+'；':''}展示码 ${esc(t.codes.join(' / ')||'未提取')}</p>${orders.length?'<details><summary>关联订单明细 · '+orders.map(o=>'第'+o['原文行号']+'行').join('、')+'</summary><p class="small">同订单可含多个商品；不代表每行都是故障商品。</p><pre>'+esc(JSON.stringify(orders,null,2))+'</pre></details>':''}</div>`;}
function drill(label,ids){const rows=all.filter(t=>ids.includes(t.row));show(label,`<p class="muted">${rows.length} 条工单 · 源表行号与原文</p>`+rows.map(mail).join(''));}
function grouped(rows,key){const map=new Map;for(const t of rows){const values=key==='codes'?t.codes:[t[key]];for(const v of new Set(values)){if(!map.has(v))map.set(v,[]);map.get(v).push(t.row);}}return [...map].map(([label,ids])=>({label,ids,count:ids.length})).sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label));}
const codeNames={'3212':'拖布阻塞','2111':'滚刷异常','2310':'尘盒 / 滤网未就位','3021':'污水箱未就位','4090':'沿墙传感器异常','5116':'通信异常','6011':'清水不足','6013':'注水装置异常','6063':'便携清洁机未就位','E23':'机器人清水水位异常','E4':'边刷异常','E41':'电池异常','E53':'TrueAI传感器异常','E5A':'陀螺仪异常','EB03':'基站集尘通道堵塞','EB1L':'加清水异常'};
const names={'Troubleshooting/Product usage':'故障 / 使用咨询','Shipping inquiry':'物流咨询'};
function chart(target,groups,denominator){if(!groups.length){$(target).innerHTML='<div class="empty">当前筛选暂无明确记录。</div>';return;}const max=Math.max(...groups.map(g=>g.count));$(target).innerHTML=`<div class="axis"><span>0</span><span>${max} 条</span></div>`+groups.map(g=>`<button class="bar" data-rows="${g.ids.join(',')}" data-label="${esc(g.label)}" aria-label="${esc(names[g.label]||g.label)}，${g.count} 条，查看源表"><span class="label">${esc(names[g.label]||g.label)}${target==='codes'?'<small>'+esc(codeNames[g.label]||'见原文报错')+'</small>':''}</span><span class="track"><span class="fill" style="width:${100*g.count/max}%"></span></span><span class="value">${g.count} 条 · ${denominator?(g.count/denominator*100).toFixed(1):'0.0'}%</span></button>`).join('');}
function renderDashboard(){const product=$('productFilter').value,rows=all.filter(t=>!product||t.product===product),fault=rows.filter(t=>t.scenario==='Troubleshooting/Product usage');$('scope').textContent=`${product||'全部产品'} · ${rows.length} 条工单 · 占比基于当前样本，非故障率`;
 chart('products',grouped(fault,'product'),fault.length);chart('scenario',grouped(rows,'scenario'),rows.length);const codes=grouped(rows,'codes');chart('codes',codes,rows.length);$('codeNote').textContent=`${rows.filter(t=>t.codes.length).length} / ${rows.length} 条含明确展示码；其余不代表无故障。一单多码时占比可重叠。`;
 const selected=new Set(rows.map(t=>t.row)),signals=[['情绪风险词组命中',advice.find(a=>a.id==='emotion').source_rows],['知识标题待核查',advice.find(a=>a.id==='knowledge').source_rows],['日期齐全可评估',advice.find(a=>a.id==='warranty').source_rows],['重复报错核查线索',advice.find(a=>a.id==='product').source_rows]];
 $('signals').innerHTML=signals.map(([label,ids])=>{ids=ids.filter(n=>selected.has(n));return `<button class="signal" data-rows="${ids.join(',')}" data-label="${label}"><span>${label}</span><b>${ids.length}<small> 条</small></b></button>`;}).join('');}
function rule(id){const rule=REPORT.rules[id];if(!rule)return;show(id+' · '+rule.name,`<p>${esc(rule.definition)}</p><p class="muted">候选归因与规则生成的建议，不是已证实根因或业务执行回执。</p>`);}
function detail(id){const a=advice.find(a=>a.id===id);if(!a)return;const coverage=REPORT.knowledge_coverage.filter(c=>a.source_rows.includes(c.row));show(a.title,`<dl class="facts"><dt>已知事实</dt><dd>${esc(a.problem)}</dd><dt>可能原因</dt><dd>${esc(a.hypothesis)}</dd><dt>待补证据</dt><dd>${esc(a.missing)}</dd><dt>贡献度</dt><dd>未估计；关联 ${a.source_rows.length} / ${all.length} 条工单（${a.sample_share}%）不等于因果贡献。</dd><dt>预期验证</dt><dd>${esc(a.expected_effect)}</dd><dt>允许动作</dt><dd>${a.allowed_actions.map(esc).join('、')}</dd><dt>禁止动作</dt><dd>${a.blocked_actions.map(esc).join('、')}</dd><dt>人工审核</dt><dd>必须；置信度低，原因待核查。</dd></dl><p><button class="rule" data-rule="${a.rule_id}">${a.rule_id} · 查看规则</button></p><h3>证据链</h3>${a.trace.map(t=>`<div class="evidence-path">${t.step}. ${esc(t.node)}<br><span class="small">${t.ref.map(esc).join('、')||'暂无充分证据'}</span></div>`).join('')}${refs(a.source_rows)}${a.id==='knowledge'?'<h3 style="margin-top:20px">同型号知识匹配</h3>'+coverage.map(c=>`<p class="small">工单第${c.row}行 · ${esc(c.pn)} / ${esc(c.code)} · ${esc(c.status)} ${c.knowledge_ids.map(k=>`<a href="/api/sources/${encodeURIComponent(k)}" target="_blank" rel="noopener">${esc(k)}</a>`).join(' ')}</p>`).join('')+'<p class="small">未命中只表示同PN公开标题匹配未命中，不把内部数字码缺少同名标题认定为知识缺失。</p>':''}`);}
function renderAdvice(){$('actions').innerHTML=advice.map(a=>`<article class="card"><div class="proposal-head"><span class="pill ${a.priority==='P1'?'priority':''}">${a.priority} · 待人工核查</span><button class="rule" data-rule="${a.rule_id}">${a.rule_id}</button></div><h2>${esc(a.title)}</h2><p class="problem">${esc(a.problem)}</p><p class="small">可能原因：${esc(a.hypothesis)}</p><div class="next">${esc(a.action)}</div><div class="meta"><b>${esc(a.owner)}</b><span>建议，未执行</span></div>${refs(a.source_rows)}<p><button class="details-link" data-advice="${a.id}">查看原因、预期效果与 Trace →</button></p></article>`).join('');
}

function tab(id){if(!['overview','attribution'].includes(id))id='overview';document.querySelectorAll('.section').forEach(n=>n.classList.toggle('active',n.id===id));document.querySelectorAll('[data-tab]').forEach(n=>{n.classList.toggle('active',n.dataset.tab===id);n.setAttribute('aria-selected',String(n.dataset.tab===id));});history.replaceState(null,'','#view='+id);}
for(const p of REPORT.statistics.product){$('productFilter').add(new Option(p.label,p.label));}$('productFilter').onchange=renderDashboard;
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.tab)tab(b.dataset.tab);if(b.dataset.row)drill('工单原文',[Number(b.dataset.row)]);if(b.hasAttribute('data-rows'))drill(b.dataset.label,b.dataset.rows.split(',').filter(Boolean).map(Number));if(b.dataset.rule)rule(b.dataset.rule);if(b.dataset.advice)detail(b.dataset.advice);});
$('close').onclick=close;$('overlay').onclick=e=>{if(e.target===$('overlay'))close();};document.addEventListener('keydown',e=>{if(e.key==='Escape')close();if(e.key==='Tab'&&$('overlay').classList.contains('open')){const nodes=[...$('overlay').querySelectorAll('button,a,summary')];if(e.shiftKey&&document.activeElement===nodes[0]){e.preventDefault();nodes.at(-1).focus();}else if(!e.shiftKey&&document.activeElement===nodes.at(-1)){e.preventDefault();nodes[0].focus();}}});renderDashboard();renderAdvice();tab(location.hash.replace('#view=',''));

// Four curated phrasings share the same facts and citations; never pretend they are model samples.
const decisionQuestion='对于目前安克创新的客服与业务经营，有什么改进建议？';
let decisionVersion=0,decisionBusy=false,decisionContext={};
const decisionVariants=[
 {intro:'建议把经营重点放在“减少重复客诉、提高处理效率、补齐知识与数据”上。当前优先处理情绪风险，再排查产品与物流体验。',order:['emotion','product','shipping','knowledge','warranty','focus'],closing:'先完成证据核查与责任分派，再用同口径指标验证改进；先解决可确认的问题，不把统计相关性当作根因。'},
 {intro:'从经营管理看，这批工单反映出三个值得核查的环节：产品排障、物流信息展示，以及知识与交接质量。建议形成按优先级推进的改进清单。',order:['shipping','product','emotion','knowledge','focus','warranty'],closing:'每项行动都要有负责人、证据和验收指标。优先级以情绪风险处置为先，其他方向通过抽查确认后安排试点。'},
 {intro:'我的建议是把客诉复盘转化为可追踪的运营任务：先处理高风险客户，再减少重复排障与查询，最后修补知识和数据完整性。',order:['emotion','knowledge','shipping','product','warranty','focus'],closing:'业务团队审核建议后开展试点，回收重开率、处理时长和知识有效召回等结果，再修订规则与 FAQ。'},
 {intro:'这批数据支持提出经营改进方向，但尚不足以认定某产品存在设计缺陷。建议围绕客户体验、支持效率和证据完整性建立责任明确的行动闭环。',order:['focus','product','shipping','emotion','knowledge','warranty'],closing:'保留原文行号和规则 ID，按优先级分派核查。用后续业务结果判断改进是否有效，而不是只看建议生成数量。'}
];
function standardDecision(version){
 const v=decisionVariants[version],fault=all.filter(t=>t.scenario==='Troubleshooting/Product usage').length,shipping=all.filter(t=>t.scenario==='Shipping inquiry').length;
 const lines=[v.intro,`数据范围：当前 ${all.length} 条工单快照，其中故障 / 使用咨询 ${fault} 条，物流咨询 ${shipping} 条。投诉日期不完整，不能判断“最近增长”；没有销量分母，不计算产品故障率。`];
 for(const [i,id] of v.order.entries()){const a=advice.find(x=>x.id===id);lines.push(`${i+1}. ${a.title}（${a.priority}）\n事实：${a.problem}\n待核查原因：${a.hypothesis}\n行动：${a.action}\n负责人：${a.owner}。${a.expected_effect}\n依据：${a.source_rows.map(r=>'工单第'+r+'行').join('、')}；规则 ${a.rule_id}。`);}
 lines.push('经营闭环：业务方提供 SOP、工单、订单、经销商与 Q&A，并明确字段含义 → 标准 Prompt 生成特定业务归因 Skill → 用已核验的 Bad Case 修订 Skill → Agent 关联产品、订单和规则 → 输出事实、假设、责任团队、行动与证据链 → 人工审核 → 回收指标并复盘。');
 lines.push('当前不足：投诉时间和部分关联字段不完整；错误码映射与知识标题覆盖需要复核；业务动作执行与效果反馈尚未接入。责任团队是建议承接团队，不代表已认定责任。');
 lines.push(v.closing+' 所有建议尚未执行；不自动退款、换货或调整质保。');return lines.join('\n\n');
}
function addDecisionMessage(role,text){const el=document.createElement('article');el.className='message '+role;const heading=document.createElement('h3');heading.textContent=role==='user'?'你的问题':'经营归因助手';const body=document.createElement('div');body.className='answer-body';body.textContent=text;el.append(heading,body);$('chatMessages').append(el);return {el,body};}
async function revealDecision(body,text){for(let i=0;i<text.length;i+=45){body.textContent=text.slice(0,i+45);$('chatMessages').scrollTop=$('chatMessages').scrollHeight;await new Promise(resolve=>setTimeout(resolve,16));}}
async function askDecision(question){if(decisionBusy||!question.trim())return;decisionBusy=true;$('sendDecision').disabled=true;$('suggestedQuestion').disabled=true;$('answerMode').disabled=true;
 const mode=$('answerMode').value==='demo'&&question===decisionQuestion?'demo':'live';
 $('chatMessages').querySelector('.welcome')?.remove();
 addDecisionMessage('user',question);const message=addDecisionMessage('assistant','');let timer;
 try{if(mode==='demo'){
  const version=decisionVersion++%4;$('chatStatus').textContent=`标准答案演示 · 版本 ${version+1}/4 · 已读取当前快照与规则，正在逐字展示`;
  await revealDecision(message.body,standardDecision(version));
  message.el.insertAdjacentHTML('beforeend',refs([...new Set(advice.flatMap(a=>a.source_rows))]));
  $('chatStatus').textContent=`标准答案演示 · 版本 ${version+1}/4 · 四种预设表达，共用事实；未调用模型`;
 }else{
  $('chatStatus').textContent='实时问答：正在请求后端模型；收到完整结果后逐字呈现（非模型 token 流）。';
  const controller=new AbortController();timer=setTimeout(()=>controller.abort(),30000);
  const response=await fetch('/api/analytics/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:question,context:decisionContext}),signal:controller.signal});
  const result=await response.json();if(!response.ok||typeof result.reply!=='string')throw new Error('unavailable');
  decisionContext=result.context||{};await revealDecision(message.body,result.reply);
  const rows=Object.keys(result.evidence||{}).map(Number).filter(n=>all.some(t=>t.row===n));message.el.insertAdjacentHTML('beforeend',refs(rows));
  if(result.trace_chain?.length){const trace=document.createElement('details');const summary=document.createElement('summary');summary.textContent='查看数据与规则执行摘要';const pre=document.createElement('div');pre.className='answer-body small';pre.textContent=result.trace_chain.map(x=>x.label+'\n'+x.definition).join('\n\n');trace.append(summary,pre);message.el.append(trace);}
  $('chatStatus').textContent=result.mode+' · 完整结果逐字展示；建议需人工复核';
 }}catch(error){message.body.textContent='本次实时问答未完成。请稍后重试，或切换“标准答案演示”后点击推荐问题。';$('chatStatus').textContent='未生成实时模型答案；没有用预设答案替代。';}
 finally{clearTimeout(timer);decisionBusy=false;$('sendDecision').disabled=false;$('suggestedQuestion').disabled=false;$('answerMode').disabled=false;}
}
$('suggestedQuestion').onclick=()=>{$('decisionInput').value=decisionQuestion;askDecision(decisionQuestion);};
$('decisionForm').onsubmit=e=>{e.preventDefault();const q=$('decisionInput').value.trim();if(q){$('decisionInput').value='';askDecision(q);}};
$('answerMode').onchange=()=>{$('chatStatus').textContent=$('answerMode').value==='demo'?'推荐问题使用四版标准答案；其他问题自动进入实时问答。':'使用服务器已配置的模型与密钥；调用失败会明确提示或标记规则摘要。';};
