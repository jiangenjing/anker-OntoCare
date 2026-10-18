/* Pure helpers: preserve factual body; no fabricated customer history. */
(function(root){
const rules=[
 [/保证退款|马上退款|guarantee.{0,12}refund|refund immediately/gi,'退款需核验购买渠道和适用规则，当前尚未办理。','Refund eligibility needs review; no refund has been processed.'],
 [/绝对没问题|100%\s*解决|100%\s*(?:resolved|guaranteed)/gi,'目前需要进一步核查。','Further review is needed.'],
 [/这不是我们的问题/gi,'理解您的困扰，我们先核对具体情况。','Let us review the issue.'],
 [/已(?:经)?(?:为您)?(?:退款|换新|赔付|发货)|(?:we have|we’ve) (?:issued a refund|shipped|replaced)/gi,'当前仅为处理建议，尚未执行。','This is a proposed action; it has not been executed.'],
 [/(?:\d+\s*[-–]\s*)?\d+\s*(?:个工作日|小时内)|within \d+ (?:hours|days)/gi,'具体时效待核验。','Timing needs verification.']
];
function checkDraft(text){return rules.flatMap(([re,zh,en],i)=>Array.from(text.matchAll(new RegExp(re.source,re.flags))).map(m=>({rule:i,text:m[0],start:m.index,end:m.index+m[0].length,suggestion:/[\u4e00-\u9fff]/.test(text)?zh:en})));}
function applySuggestions(text){return checkDraft(text).reverse().reduce((s,h)=>s.slice(0,h.start)+h.suggestion+s.slice(h.end),text);}
function rewriteTone(text,tone){
 const zh=/[\u4e00-\u9fff]/.test(text);
 const greetings=zh?{formal:'您好，感谢您的来信。',friendly:'你好，谢谢你把情况告诉我们。',concise:'你好，',empathetic:'你好，我们理解这件事给你带来的困扰。'}:{formal:'Dear Customer, Thank you for your message.',friendly:'Hi, thank you for sharing the details with us.',concise:'Hello,',empathetic:'Hello, we understand how frustrating this situation can be.'};
 if(!greetings[tone])return text;
 const body=text.replace(/^(?:你好，\s*感谢你联系我们。|Hello,\s*Thank you for contacting us\.)\s*/,'');
 return greetings[tone]+'\n\n'+body;
}
function emotion(text){
 const score=/furious|angry|outrage|\b(?:shit|bullshit|fuck\w*|scam)\b|complain|ridiculous|unacceptable|lawyer|better business|投诉|差评|起诉|气死|太差|生气|!!!/i.test(text)?9:/frustrat|worried|still waiting|urgent|asap|in a hurry|担心|着急|赶紧|失望/i.test(text)?5:2;
 return {score,label:score>=9?'投诉风险':score>=7?'不满':score>=4?'担忧':'未发现明显负面词',basis:'关键词提示，非心理判断'};
}
const api={checkDraft,applySuggestions,rewriteTone,emotion};
if(typeof module!=='undefined')module.exports=api;root.MailAssist=api;
})(typeof globalThis==='undefined'?window:globalThis);
