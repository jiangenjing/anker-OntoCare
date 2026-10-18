/* Read-only attribution engine: observations and proposals, never business execution. */
(function(root){
'use strict';
const RULES={
 'DO-RC1':{tag:'RC1',name:'上下文丢失',definition:'邮件明确提及重复提交相同信息。需要核查完整交接记录。'},
 'DO-RC2':{tag:'RC2',name:'规则散落',definition:'邮件明确提及同条件下政策或答复不一致。需要核查适用政策版本。'},
 'DO-RC3':{tag:'RC3',name:'产品设计核查',definition:'同一型号错误码重复，或不同型号同码且邮件均明确描述同类拖布阻塞症状，进入低置信度调查候选；跨型号必须分别复现，不证明共用设计缺陷。'},
 'DO-RC4':{tag:'RC4',name:'过保临界点',definition:'明确投诉日期位于对应 SKU 质保结束后 1–30 天。不能用今天或购买日期替代投诉日期。'},
 'DO-OPS-KNOWLEDGE':{name:'知识覆盖核查',definition:'错误码必须匹配同 PN 的公开知识标题；未匹配进入人工知识核查，不跨型号补答案。'},
 'DO-OPS-SHIPPING':{name:'物流分件核查',definition:'物流咨询按订单和商品明细关联快照，不能把历史记录当作实时结果。'},
 'DO-OPS-WARRANTY':{name:'质保日期核验',definition:'分别记录投诉日期与同SKU质保日期；缺日期不可推定过保集中。提示策略需由业务审核，不自动延保或推销。'},
 'DO-OPS-EMOTION':{name:'情绪风险核查',definition:'按明确投诉/愤怒词组标记邮件线索，人工复核语境；情绪不改变退款、保修资格。'},
 'DO-OPS-FOCUS':{name:'高频产品抽查',definition:'工单量用于安排抽查，不作为故障率、退货率或毛利率。'}
};
const ref=rows=>[...new Set(rows)].sort((a,b)=>a-b).map(n=>'客诉工单信息表第'+n+'行');
function aggregate(rows,key){const g={};for(const r of rows)for(const label of (key==='codes'?r.codes:[r[key]])){if(!g[label])g[label]=[];if(!g[label].includes(r.row))g[label].push(r.row)}return Object.entries(g).map(([label,ids])=>({label,count:ids.length,share:Number((ids.length/rows.length*100).toFixed(1)),source_rows:ids,source_trace:ref(ids)})).sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label,'en'))}
function attributeToRootCause(finding){
 const tag=finding.rc_tag,rid='DO-'+tag;if(!RULES[rid])return null;
 const direct=tag==='RC4';return {id:'A-'+finding.id,finding_id:finding.id,rc_tag:tag,rc_name:RULES[rid].name,confidence:direct?'medium':'low',status:'待人工核查',rule_id:rid,evidence_rows:finding.source_rows,source_trace:ref(finding.source_rows),audit_summary:{fact:finding.observation,hypothesis:finding.hypothesis,verification:finding.verification,conclusion:direct?'符合30天分析窗口，提交政策核查；不自动延长质保。':'存在核查线索，尚不能确认根因或责任。',confidence:direct?'medium':'low'}};
}
function generateActions(a){const config={RC1:['核对工单交接摘要与重复索取字段，补齐已确认信息。','客服系统团队'],RC2:['核对同一地区、渠道的政策版本与回复记录，统一适用条件。','客服运营团队'],RC3:['按相同型号和错误码抽查复现条件、维护步骤及批次，再决定是否提交工程调查。','产品团队 + 技术支持'],RC4:['人工核验投诉时间、购买凭证与适用政策，提供清晰的保修处理路径。','售后政策团队']}[a.rc_tag];return {id:'ACT-'+a.id,attribution_id:a.id,action:config[0],owner:config[1],priority:a.confidence==='low'?'P2':'P1',expected_impact:'预期减少重复核查；效果需通过后续处理时长、重开率验证，当前不估算降幅。',source_trace:a.source_trace,source_rows:a.evidence_rows,rule_id:a.rule_id,deadline:'负责人确认后排期',status:'建议，未执行'}};
function analyzeComplaints(snapshot){
 const rows=snapshot.tickets,N=rows.length,statistics=Object.fromEntries(['scenario','product','product_line','codes','region'].map(k=>[k,aggregate(rows,k)]));
 const coverage=[];for(const r of rows)for(const code of r.codes){const ids=snapshot.knowledge.filter(k=>k.visible&&r.pn&&k.pn.includes(r.pn)&&new RegExp('(^|[^A-Z0-9])'+code+'([^A-Z0-9]|$)','i').test(k.title)).map(k=>k.id);coverage.push({row:r.row,product:r.product,pn:r.pn,code,knowledge_ids:ids,status:!r.pn?'型号待确认':ids.length?'同型号知识已匹配':'待核查知识覆盖',source_trace:ref([r.row])})}
 const findings=[];for(const [dimension,key] of [['问题类型','scenario'],['产品名称','product'],['产品线','product_line'],['错误码','codes']])for(const b of statistics[key].slice(0,3))findings.push({id:'F'+String(findings.length+1).padStart(3,'0'),dimension,...b,trend:null,...(key==='codes'?{coverage:coverage.filter(c=>c.code===b.label)}:{})});
 const signals=[];const patterns={RC1:/repeat myself|retell|already (?:provided|sent).{0,50}(?:again|ask)|重复(?:提交|提供|描述)|每次.{0,10}重新.{0,10}(?:讲|说)/i,RC2:/inconsistent|different (?:answers?|resolution)|contradict|政策前后不一致|说法不一|政策.{0,8}冲突/i};
 for(const [tag,p] of Object.entries(patterns)){const hit=rows.filter(r=>p.test(r.email));if(hit.length)signals.push({id:tag,rc_tag:tag,source_rows:hit.map(r=>r.row),observation:hit.length+' 条邮件明确出现'+RULES['DO-'+tag].name+'相关表述。',hypothesis:RULES['DO-'+tag].name+'可能影响处理体验。',verification:'有首封邮件陈述；尚需完整会话、交接日志和适用政策版本核验。'})}
 const repeated={};for(const c of coverage)if(c.pn){const k=c.pn+' / '+c.code;if(!repeated[k])repeated[k]=[];repeated[k].push(c)}
 for(const [k,group] of Object.entries(repeated)){const ids=[...new Set(group.map(x=>x.row))];if(ids.length>=2)signals.push({id:'RC3-'+k.replaceAll(' / ','-'),rc_tag:'RC3',source_rows:ids,observation:k+' 在 '+ids.length+' 个工单出现。',hypothesis:'可能存在共性的使用、维护或产品故障因素。',verification:'同 PN、同错误码可复核；尚无批次、复现、工程结论及销量分母，不能认定设计缺陷或多个独立客户。'})}
 // Cross-model candidates require matching symptom evidence as well as a repeated code.
 for(const bucket of statistics.codes.filter(b=>b.count>=2)){
  const matching=rows.filter(r=>bucket.source_rows.includes(r.row)&&r.pn&&/mop[\s\S]{0,70}(?:stuck|obstruct|block|vast|verstopt)/i.test(r.email));
  if(new Set(matching.map(r=>r.pn)).size>=2)signals.push({id:'RC3-CROSS-'+bucket.label,rc_tag:'RC3',source_rows:matching.map(r=>r.row),observation:matching.map(r=>r.product+' / '+r.pn).join('、')+' 的 '+matching.length+' 条工单均包含 '+bucket.label+' 和拖布阻塞描述。',hypothesis:'可能存在相似的维护或运行条件，需按型号分别核查；不能推定共用部件或同一根因。',verification:'原信可核对错误码和症状，但型号不同；需分别复现并排除使用、运输及个体故障。'})
 }
 let eligible=0;const near=[];for(const r of rows){if(!r.complaint_date||!r.warranty_end)continue;const a=Date.parse(r.complaint_date),b=Date.parse(r.warranty_end);if(!Number.isFinite(a)||!Number.isFinite(b))continue;eligible++;const days=(a-b)/86400000;if(days>0&&days<=snapshot.policy.rc4_days_after_expiry)near.push({row:r.row,days})}
 if(near.length)signals.push({id:'RC4',rc_tag:'RC4',source_rows:near.map(x=>x.row),observation:near.length+' 条工单的明确投诉日期处于到期后30天内。',hypothesis:'质保边界可能影响客户预期。',verification:'对照明确投诉日期与同 SKU 质保截止；仍需凭证、渠道和地区政策。'})
 const attributions=signals.map(attributeToRootCause),actions=attributions.map(generateActions),gaps=coverage.filter(c=>!c.knowledge_ids.length);
 const operational=(id,action,owner,ids,rid)=>({id,attribution_id:null,action,owner,priority:'P2',expected_impact:'预期减少重复查询；通过后续工单重开率及平均处理时长验证，不预填改善百分比。',source_trace:ref(ids),source_rows:ids,rule_id:rid,deadline:'负责人确认后排期',status:'建议，未执行'});
 if(gaps.length)actions.push(operational('ACT-KNOWLEDGE','逐条核对型号及错误码知识覆盖，补齐可审核的排障条目与适用条件。','知识运营 + 技术支持',gaps.map(c=>c.row),'DO-OPS-KNOWLEDGE'));
 const shipping=rows.filter(r=>r.scenario==='Shipping inquiry');if(shipping.length)actions.push(operational('ACT-SHIPPING','在订单卡片逐件显示物流记录，并核对客户实际收到的商品，优先处理拆单和记录冲突。','物流运营 + 客服',shipping.map(r=>r.row),'DO-OPS-SHIPPING'));
 if(statistics.product[0])actions.push(operational('ACT-FOCUS','按高频产品抽查原文、已尝试步骤和现有知识，确认问题是否可复现。','产品运营 + 客服',statistics.product[0].source_rows,'DO-OPS-FOCUS'));
 const codeTop=statistics.codes.slice(0,3),top=statistics.scenario[0];const summary={total_tickets:N,high_risk_scenarios:signals.length,top_issue:top?top.label+'（'+top.share+'%）':'未提供',top_product_line:statistics.product_line[0]?.label||'未提供',top_products:statistics.product.slice(0,3),critical_finding:signals.filter(s=>s.rc_tag==='RC3').length+' 组重复故障候选待核查；跨型号分别验证，不能直接认定为设计缺陷。',recommended_actions:actions.length,source_trace:ref(rows.map(r=>r.row))};
 const used=new Set(coverage.flatMap(c=>c.knowledge_ids));return {report_type:'operations_snapshot_report',period:'全量已提供工单快照；不限定自然周',generated_at:new Date().toISOString(),executive_summary:summary,statistics,findings,attributions,actions,rc_counts:Object.fromEntries(['RC1','RC2','RC3','RC4'].map(k=>[k,new Set(attributions.filter(a=>a.rc_tag===k).flatMap(a=>a.evidence_rows)).size])),warranty_window:{days:30,assessable_tickets:eligible,confirmed_candidates:near.length,unassessed_tickets:N-eligible,source_rows:near.map(x=>x.row),assessable_rows:rows.filter(r=>r.complaint_date&&r.warranty_end&&Number.isFinite(Date.parse(r.complaint_date))&&Number.isFinite(Date.parse(r.warranty_end))).map(r=>r.row)},knowledge_gaps:gaps,knowledge_coverage:coverage,top_error_codes:codeTop,tickets:rows,order_snapshot:snapshot.orders,knowledge_sources:snapshot.knowledge.filter(k=>used.has(k.id)),rules:RULES,source_trace:snapshot.source_trace,source_counts:snapshot.source_counts,data_quality_note:'统计对象为已提供的全量样本。投诉时间仅在明确记录且对应SKU可关联时参与临界判断；地区仅取邮件明示国家。没有销量、售后成本和历史期数据，因此不计算故障率、利润影响或环比。',implementation:'源表聚合 + 显式候选规则；当前摘要为可复算模板生成，不调用LLM，不执行退款、换货或外部发送。'};
}
function exportWeeklyReport(r){const s=r.executive_summary;const lines=['# 安克售后经营摘要 · 全量快照','', '> '+r.period,'','## 一、核心结论','',`本次样本共 ${s.total_tickets} 件，${s.top_issue} 是主要咨询场景。`,'产品名前三：'+s.top_products.map(x=>x.label+'（'+x.count+'件）').join('、')+'。产品线按源表A列单独统计。',s.critical_finding,`过保临界窗口：${r.warranty_window.assessable_tickets} 件具备明确日期及同SKU关联条件，其中 ${r.warranty_window.confirmed_candidates} 件符合到期后30天窗口；其余逐单补充时间证据后复核。`,'来源：'+s.source_trace.join('、'),'','## 二、关键洞察',''];
 for(const a of r.attributions)lines.push('### '+a.rc_name+' · '+a.confidence,a.audit_summary.fact,a.audit_summary.conclusion,'依据：'+a.source_trace.join('、'),'规则：'+a.rule_id,'');
 lines.push('## 三、建议行动','','| 行动 | 归属团队 | 优先级 | 预期收益 | 排期 |','|---|---|---|---|---|');for(const a of r.actions)lines.push(`| ${a.action} | ${a.owner} | ${a.priority} | ${a.expected_impact} | ${a.deadline} |`);lines.push('');for(const a of r.actions)lines.push(a.id+' · '+a.rule_id+' · '+a.source_trace.join('、'));lines.push('','## 四、系统价值与适用范围','','将工单事实、候选归因、责任团队和核查动作串联，支持经营复盘。建议展示不代表业务动作已经执行。',r.data_quality_note);return lines.join('\n')}
const api={analyzeComplaints,attributeToRootCause,generateActions,exportWeeklyReport,RULES};if(typeof module!=='undefined')module.exports=api;else root.MerchantAttribution=api;
if(typeof require!=='undefined'&&require.main===module){const fs=require('fs'),path=require('path'),s=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),r=analyzeComplaints(s);r.improvement_advice=require('../scripts/merchant_attribution/insights.js').proposals(r);fs.writeFileSync(path.join(process.argv[3],'attribution_report.json'),JSON.stringify(r,null,2));fs.writeFileSync(path.join(process.argv[3],'weekly_report.md'),exportWeeklyReport(r))}
})(typeof globalThis!=='undefined'?globalThis:this);
