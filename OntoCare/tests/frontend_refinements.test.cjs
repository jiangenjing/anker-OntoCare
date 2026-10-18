const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const graph=require('../static/conversation-graph.js');
const mail=require('../static/mail-presentation.js');

test('two actual order/product entities produce two nodes and one association',()=>{
  const data={followups:{ontology:{intent:'shipping',product:'T2080',nodes:[
    {id:'case',type:'ServiceCase'},{id:'T2080',type:'Product'},{id:'ANKER002',type:'Order'},
    {id:'order-3',type:'OrderItem'},{id:'order-4',type:'OrderItem'},{id:'service-rules',type:'Policy'}]}},
    trace:{product:'S1 Pro 扫地机'},citations:[{id:'strategy',kind:'strategy'}]};
  const before=JSON.stringify(data),result=graph.normalize(data);
  assert.deepEqual(result.nodes.map(node=>node.type),['Order','Product']);
  assert.equal(result.edges.length,1);assert.equal(JSON.stringify(data),before);
});

test('knowledge recommendations and initial demo orders are excluded from the dialogue graph',()=>{
  const initial=graph.normalize({followups:{ontology:{nodes:[{id:'order-5',type:'OrderItem'}]}}});
  assert.equal(initial.nodes.length,0);
  const result=graph.normalize({followups:{ontology:{product:'T2080',intent:'troubleshooting',nodes:[
    {id:'T2080',type:'Product'},{id:'r-482',type:'KnowledgeItem'},{id:'r-426',type:'KnowledgeItem'}]}},
    trace:{order:'ANKER002'},citations:[{id:'r-482',kind:'knowledge',title:'T2080 EB1L adding water error',url:'/api/sources/r-482'}]});
  assert.deepEqual(result.nodes.map(node=>node.id),['T2080','r-482']);
});

test('history retains multiple message sources without fabricating links between different turns',()=>{
  const first={turn:1,messageId:'chat-user-1',message:'订单',nodes:[{key:'Order:A',id:'A',type:'Order'}],edges:[]};
  const second={turn:2,messageId:'chat-user-2',message:'产品',nodes:[{key:'Product:T',id:'T',type:'Product'}],edges:[]};
  let result=graph.combine([first,second]);assert.equal(result.edges.length,0);
  result=graph.combine([first,{...first,turn:3,messageId:'chat-user-3',message:'再次查订单'}]);
  assert.equal(result.nodes.length,1);assert.deepEqual(result.nodes[0].sources.map(source=>source.messageId),['chat-user-1','chat-user-3']);
});

test('citation-free email display retains byte-identical text for existing AI edit requests',()=>{
  const textarea={value:''},view=mail.create(textarea),raw='Dear Customer,\n\nPlease share order Anker002. [2]\n\nBest regards';
  view.references([{},{}]);view.write(raw);
  assert.equal(textarea.value,'Dear Customer,\n\nPlease share order Anker002.\n\nBest regards');
  assert.equal(view.readRaw(),raw);
});

test('ordinary bracketed values and citations outside the actual source list are preserved',()=>{
  const result=mail.project('Batch [2026], item [8]; source [2].',2);
  assert.equal(result.clean,'Batch [2026], item [8]; source.');
});

test('editing a visible paragraph preserves hidden citation markers in the canonical draft',()=>{
  const textarea={value:''},view=mail.create(textarea);view.references([{},{}]);
  view.write('Please share order Anker002. [2]\nThanks.');
  textarea.value='Please share order Anker003.\nThanks.';
  assert.equal(view.readRaw(),'Please share order Anker003. [2]\nThanks.');
  textarea.value='An entirely edited reply.';
  assert.match(view.readRaw(),/\[2\]/);
});

test('partial email selection maps to the same cited paragraph for the existing rewrite endpoint',()=>{
  const textarea={value:''},view=mail.create(textarea),raw='First paragraph. [1]\n\nSecond paragraph. [2]';
  view.references([{},{}]);view.write(raw);
  const end=textarea.value.indexOf('\n');const range=view.rawRange([0,end]);
  assert.equal(view.readRaw().slice(...range),'First paragraph. [1]');
});

function newChatFixture(active=false){
  let next=0;const nodes=new Map(),resets=[],loads=[],storage=[];
  function node(id){if(!nodes.has(id))nodes.set(id,{value:'old',hidden:false,open:true,
    replaceChildren(...children){this.children=children;},focus(){this.focused=true;}});return nodes.get(id);}
  const context={sending:active,mediaUploading:false,sid:'old-session',ticketContext:{order_id:'ANKER002'},pendingImg:'old.png',latestFollowups:{old:true},lang:'zh',
    crypto:{randomUUID:()=> 'new-session-'+(++next)},sessionStorage:{setItem:(...entry)=>storage.push(entry)},
    document:{getElementById:node,createElement:()=>({style:{}}),querySelector:()=>null},
    ontologyGraph:{reset:id=>resets.push(id)},renderOrderDetails(){},setLang(){},loadInitialOptions:()=>loads.push(context.sid)};
  const html=fs.readFileSync(require.resolve('../static/index.html'),'utf8');
  vm.createContext(context);vm.runInContext(html.slice(html.indexOf('function startNewChat(){'),html.indexOf('function loadInitialOptions(){')),context);
  return{context,node,resets,loads,storage};
}

test('new chat creates an independent session and clears every prior conversation attachment',()=>{
  const f=newChatFixture();f.context.startNewChat();
  assert.equal(f.context.sid,'new-session-1');assert.equal(f.context.pendingImg,null);
  assert.equal(Object.keys(f.context.ticketContext).length,0);assert.equal(f.context.latestFollowups,null);
  assert.equal(f.node('in').value,'');assert.equal(f.node('handoff').hidden,true);
  assert.deepEqual(f.resets,['new-session-1']);assert.deepEqual(f.loads,['new-session-1']);
  f.context.startNewChat();assert.equal(f.context.sid,'new-session-2');
});

test('an active reply cannot leak into a new chat through a mid-stream reset',()=>{
  const f=newChatFixture(true);f.context.startNewChat();
  assert.equal(f.context.sid,'old-session');assert.equal(f.resets.length,0);
});
