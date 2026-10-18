const a=require('../static/merchant_assist.js'),assert=require('node:assert/strict');
const body='ANKER002 T2080GA1 $20 2026-10-16 Delivered [1]';
for(const tone of ['formal','friendly','concise','empathetic'])assert(a.rewriteTone('Hello,\n\nThank you for contacting us.\n\n'+body,tone).endsWith(body));
assert.notEqual(a.rewriteTone(body,'formal'),a.rewriteTone(body,'empathetic'));
assert.equal(a.checkDraft('马上退款，3-5个工作日到账').length,2);
assert(!a.applySuggestions('马上退款，3-5个工作日到账').includes('3-5'));
assert(a.emotion('FURIOUS').score>a.emotion('Hello').score);
assert.equal(a.checkDraft('需要核查退款资格').length,0);
console.log('merchant helper checks passed');
