const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const suggestions=require('../static/suggestions.js');
const graph=require('../static/conversation-graph.js');

test('initial suggestions span parcels and two source-backed product diagnostics',()=>{
  const rows=suggestions.select({ontology:{revision:0}});
  assert.equal(rows.length,3);
  assert.match(rows[0].text,/Anker002/);assert.match(rows[1].text,/T2080.*EB1L/);
  assert.match(rows[2].text,/T8D04/);
});
test('shipping suggestions cover evidence mismatch and service documents for the actual order',()=>{
  const rows=suggestions.select({ontology:{revision:2,intent:'shipping',product:'T2351',nodes:[{type:'Order',id:'ANKER013'}]}});
  assert.equal(rows.length,3);assert.ok(rows.every(row=>row.text.includes('ANKER013')));
  assert.match(rows[1].text,/实际收货/);assert.match(rows[2].text,/购买凭证/);
});
test('presentation retains required guided workflow answers and omits already asked questions',()=>{
  const data={ontology:{revision:1},quick_replies:[{text:'试过了，还是不行'},{text:'解决了'},{text:'这一步怎么做？'}]};
  assert.deepEqual(suggestions.select(data).map(q=>q.text),data.quick_replies.map(q=>q.text));
  assert.equal(suggestions.select(data,{asked:['解决了']}).length,2);
});
test('policy and review nodes require actual citations, not merely recommended sources',()=>{
  const ontology={nodes:[{id:'service-rules',type:'Policy'},{id:'s-1',type:'ReviewStrategy'}]};
  assert.equal(graph.normalize({followups:{ontology},citations:[]}).nodes.length,0);
  const result=graph.normalize({followups:{ontology},citations:[{id:'service-rules',kind:'context'},{id:'s-1',kind:'strategy'}]});
  assert.deepEqual(result.nodes.map(node=>node.type),['Policy','ReviewStrategy']);
});
test('a found order remains linked to product knowledge during later troubleshooting',()=>{
  const data={followups:{ontology:{product:'T2080',intent:'troubleshooting'}},
    trace:{order:'ANKER002',order_status:'FOUND'},citations:[{id:'r-482',kind:'knowledge',title:'EB1L'}]};
  assert.deepEqual(graph.normalize(data).nodes.map(node=>node.type),['Order','Product','KnowledgeItem']);
  data.trace.order_status='NOT_FOUND';assert.ok(graph.normalize(data).nodes.every(node=>node.type!=='Order'));
});

function merchantFixture(){
  const elements=new Map(),requests=[];let raw='Guten Tag, Ihre Bestellung Anker007 ist noch nicht bestätigt. [2]';
  function node(id){if(!elements.has(id))elements.set(id,{value:'',hidden:false,textContent:'',classList:{toggle(){}},replaceChildren(){},append(){},addEventListener(name,fn){this[name]=fn;}});return elements.get(id);}
  node('translateLang').value='zh';node('subject').value='Betreff: Ihre Anfrage';
  const context={state:{currentLanguage:'de',currentTone:null,originalDraft:raw},busy:false,
    $:node,getDraft:()=>raw,setDraft:text=>{raw=text;},draftView:{rawRange:span=>span},
    document:{querySelectorAll:()=>[],createElement:()=>node('generated')},window:{},
    fetch:async(url,options)=>{requests.push(JSON.parse(options.body));return{ok:true,json:async()=>context.response};}};
  vm.createContext(context);vm.runInContext(fs.readFileSync(require.resolve('../static/merchant_extra.js'),'utf8'),context);
  return{context,node,requests,raw:()=>raw};
}
test('versions and tone keep the current German language even when translation target is Chinese',async()=>{
  const f=merchantFixture();f.context.response={short:'Kurz',standard:'Standard',detailed:'Ausführlich'};
  await f.node('makeVersions').onclick();assert.equal(f.requests[0].language,'de');
  f.context.response={text:'Freundlicher Text'};await f.context.window.MerchantExtra.tone('friendly');
  assert.equal(f.requests[1].language,'de');
});
test('explicit translation atomically updates subject, body, current language and invalidates old versions',async()=>{
  const f=merchantFixture();f.context.response={short:'A',standard:'B',detailed:'C'};await f.node('makeVersions').onclick();
  f.context.response={subject:'关于您的咨询',text:'您好，订单仍需核查。'};
  await f.node('translate').onclick();assert.equal(f.requests[1].language,'zh');
  assert.equal(f.requests[1].subject,'Betreff: Ihre Anfrage');
  assert.equal(f.node('subject').value,'关于您的咨询');assert.equal(f.raw(),'您好，订单仍需核查。');
  assert.equal(f.context.state.currentLanguage,'zh');assert.equal(f.node('versions').hidden,true);
  f.context.window.MerchantExtra.restore();assert.equal(f.context.state.currentLanguage,'de');
  assert.equal(f.node('subject').value,'Betreff: Ihre Anfrage');assert.equal(f.raw(),'B');
});
test('failed language validation preserves the prior subject, draft and current language',async()=>{
  const f=merchantFixture(),before=f.raw();f.context.fetch=async()=>({ok:false,json:async()=>({error:'语言检查未通过'})});
  await f.node('translate').onclick();assert.equal(f.raw(),before);assert.equal(f.context.state.currentLanguage,'de');
  assert.equal(f.node('subject').value,'Betreff: Ihre Anfrage');assert.equal(f.node('status').textContent,'语言检查未通过');
});
