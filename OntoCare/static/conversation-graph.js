/* A read-only projection of existing dialogue results; never calls a model or changes a case. */
(function(root){
  const COLORS={Order:'#0d9488',Product:'#6366f1',KnowledgeItem:'#d58a22',Policy:'#c75b83',ReviewStrategy:'#8073c2'};
  const valid=value=>typeof value==='string'&&value&&!['未提供','未确定','UNKNOWN','NONE'].includes(value);
  function normalize(data){
    const ontology=data.followups?.ontology||{},trace=data.trace||{},snapshot=data.order_snapshot||data.order_card;
    const nodes=[],citations=Array.isArray(data.citations)?data.citations:[];
    const raw=Array.isArray(ontology.nodes)?ontology.nodes:[];
    function add(id,type,label,description,reference){
      if(!valid(id)||nodes.some(node=>node.id===id&&node.type===type))return;
      nodes.push({key:type+':'+id,id,type,label,description:description||'',reference:reference||null});
    }
    const oid=raw.find(node=>node.type==='Order')?.id||
      (trace.order_status==='FOUND'&&valid(trace.order)?trace.order:null)||
      (['shipping','warranty','return'].includes(ontology.intent)&&valid(trace.order)?trace.order:null)||
      (!data.followups?snapshot?.order_id:null);
    if(oid)add(oid,'Order',oid,'订单信息 · '+(trace.order_status==='NOT_FOUND'?'尚未查到记录':'资料快照，归属尚未核验'));
    const product=raw.find(node=>node.type==='Product')?.id||ontology.product;
    if(valid(product))add(product,'Product',valid(trace.product)?trace.product:product,'产品型号 · '+product);
    for(const citation of citations){
      if(citation.id==='service-rules')add(citation.id,'Policy','售后服务规则','仅展示本次答复实际引用的服务规则',{url:citation.url,label:citation.label});
      if(citation.kind==='strategy'&&raw.some(node=>node.type==='ReviewStrategy'&&node.id===citation.id))add(citation.id,'ReviewStrategy','补充核查策略',citation.label||citation.title,{url:citation.url,label:citation.label});
      if(citation.kind!=='knowledge')continue;
      const code=String(citation.title||'').match(/\b(EB[A-Z0-9]{1,3}|E\d[A-Z0-9]{0,3})\b/);
      add(citation.id,'KnowledgeItem',code?code[1]+' 排障资料':'产品知识',citation.title||citation.label||citation.id,
        {url:citation.url,label:citation.label});
    }
    // A projected edge means these entities participated in the same turn.
    const edges=nodes.slice(1).map(node=>({from:nodes[0].key,to:node.key,relation:'same_turn'}));
    return {nodes,edges};
  }
  function combine(records){
    const nodes=new Map(),edges=new Map();
    for(const record of records){
      for(const node of record.nodes){
        const merged=nodes.get(node.key)||{...node,sources:[]};
        Object.assign(merged,node);
        if(!merged.sources.some(source=>source.turn===record.turn))merged.sources.push({turn:record.turn,messageId:record.messageId,message:record.message});
        nodes.set(node.key,merged);
      }
      for(const edge of record.edges){
        if(!record.nodes.some(node=>node.key===edge.from)||!record.nodes.some(node=>node.key===edge.to))continue;
        const key=[edge.from,edge.to].sort().join('|');
        if(!edges.has(key))edges.set(key,{...edge,turns:[]});
        edges.get(key).turns.push(record.turn);
      }
    }
    return {nodes:[...nodes.values()],edges:[...edges.values()]};
  }
  function positions(count){
    if(count===1)return {height:200,points:[{x:170,y:100}]};
    if(count===2)return {height:220,points:[{x:84,y:110},{x:256,y:110}]};
    if(count===3)return {height:280,points:[{x:170,y:60},{x:84,y:205},{x:256,y:205}]};
    return {height:Math.ceil(count/2)*130,points:Array.from({length:count},(_,i)=>({x:i%2?256:84,y:60+Math.floor(i/2)*130}))};
  }
  function mount({element,log,sessionId,storage}){
    let records=[],selected=null,sequence=0,lastMessage=null,language='zh',key='';
    const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
    const svg=(tag,attrs)=>{const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs||{}))node.setAttribute(k,String(v));return node;};
    const text=(zh,en)=>language==='en'?en:zh;
    const types={Product:['产品','Product'],Order:['订单','Order'],KnowledgeItem:['知识','Knowledge'],Policy:['规则','Policy'],ReviewStrategy:['核查','Review']};
    function typeLabel(type){return types[type]?.[language==='en'?1:0]||type;}
    const heading=el('div',undefined,'ontology-heading'),title=el('h2','对话本体'),eyebrow=el('span','Service Ontology','ontology-eyebrow');
    heading.append(el('div'));heading.firstChild.append(eyebrow,title);
    const counter=el('span','0','ontology-count');heading.append(counter);
    const subtitle=el('p','只展示当前对话关联的信息','ontology-subtitle');
    const canvas=el('div',undefined,'ontology-canvas');canvas.setAttribute('aria-label','会话信息关联图');
    const legend=el('div',undefined,'ontology-legend'),detail=el('section',undefined,'ontology-detail');
    const status=el('p','点击节点，定位到关联提问','ontology-status');status.setAttribute('role','status');
    const mobile=el('details',undefined,'ontology-mobile');mobile.open=true;
    const mobileTitle=el('summary','对话本体 · 点击查看');
    const content=el('div',undefined,'ontology-content');content.append(heading,subtitle,canvas,legend,detail,status);
    mobile.id='judge-ontology-sheet';mobile.append(mobileTitle,content);element.replaceChildren(mobile);
    const graphToggle=el('button','图谱 · 0','mobile-graph-toggle');graphToggle.type='button';graphToggle.setAttribute('aria-controls',mobile.id);graphToggle.setAttribute('aria-expanded','false');
    document.querySelector('.chat-head').insertBefore(graphToggle,document.getElementById('newChat'));
    graphToggle.onclick=()=>{mobile.open=!mobile.open;};
    mobile.addEventListener('toggle',()=>graphToggle.setAttribute('aria-expanded',String(mobile.open)));

    const narrow=window.matchMedia('(max-width: 800px)');mobile.open=!narrow.matches;narrow.addEventListener('change',event=>{mobile.open=!event.matches;});
    function save(){try{storage?.setItem(key,JSON.stringify({records}));}catch{}}
    function reset(id){key='ontocare_graph_'+id;records=[];selected=null;lastMessage=null;sequence=0;render();}
    function registerMessage(message){message.id='chat-user-'+(++sequence);message.tabIndex=-1;lastMessage=message;}
    function jump(source){
      const target=document.getElementById(source.messageId);
      if(!target||!log.contains(target)){status.textContent=text('关联消息不在当前会话中。','The message is not in this conversation.');return;}
      const top=target.getBoundingClientRect().top-log.getBoundingClientRect().top+log.scrollTop-Math.max(20,(log.clientHeight-target.offsetHeight)/2);
      log.scrollTo({top:Math.max(0,top),behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
      target.focus({preventScroll:true});target.classList.add('message-linked');if(narrow.matches)mobile.open=false;
      setTimeout(()=>target.classList.remove('message-linked'),1800);
      status.textContent=text('已定位到第 '+source.turn+' 轮提问','Located question in turn '+source.turn);
    }
    function showDetail(node){
      detail.replaceChildren();if(!node)return;
      detail.append(el('strong',node.label),el('p',node.description));
      const list=el('div',undefined,'ontology-source-list');
      for(const source of [...node.sources].reverse()){
        const button=el('button',text('第 '+source.turn+' 轮 · ','Turn '+source.turn+' · ')+source.message);button.type='button';button.title=source.message;
        button.onclick=()=>jump(source);list.append(button);
      }
      detail.append(list);
      if(node.reference?.url){
        try{const url=new URL(node.reference.url,location.href);if(url.origin===location.origin&&url.pathname.startsWith('/api/sources/')){
          const link=el('a',text('查看引用原文 ↗','Open source ↗'));link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';detail.append(link);
        }}catch{}
      }
    }
    function icon(type){
      const view=svg('svg',{viewBox:'0 0 24 24',width:22,height:22,fill:'none',stroke:'currentColor','stroke-width':1.6,'aria-hidden':'true'});
      const paths={Product:['M12 3 3 8l9 5 9-5-9-5Z','M3 8v9l9 5 9-5V8','M12 13v9','m7 5 10 5'],Order:['M7 3h10l3 3v15H4V3h3Z','M8 8h8M8 12h8M8 16h5'],Policy:['M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z','m8 12 3 3 5-6'],ReviewStrategy:['M4 6h16M4 12h16M4 18h16','M8 3v6M16 9v6M10 15v6'],KnowledgeItem:['M12 5C8 2 3 4 3 4v16s5-2 9 1c4-3 9-1 9-1V4s-5-2-9 1Z','M12 5v16']};
      for(const d of paths[type]||paths.KnowledgeItem)view.append(svg('path',{d,'stroke-linecap':'round','stroke-linejoin':'round'}));return view;
    }
    function render(){
      title.textContent=text('对话本体','Conversation graph');subtitle.textContent=text('全部对话 · 点击节点回到对应提问','All conversations · Select a node to revisit a question');
      const graph=combine(records);
      graphToggle.textContent=text('图谱 · ','Graph · ')+graph.nodes.length;counter.textContent=graph.nodes.length;mobileTitle.textContent=text('对话本体','Conversation graph')+(graph.nodes.length?' · '+graph.nodes.length+text(' 项信息',' items'):'');
      canvas.replaceChildren();legend.replaceChildren();
      if(!graph.nodes.length){
        canvas.style.height='220px';const empty=el('div',undefined,'ontology-empty');const visual=el('div',undefined,'ontology-empty-dots');visual.setAttribute('aria-hidden','true');visual.append(el('i'),el('i'),el('i'));
        empty.append(visual,el('strong',text('让服务依据，看得见','See the evidence behind the answer')),el('p',text('发出第一句提问，连接你的产品、订单与知识。','Products, orders and cited knowledge will appear here.')));canvas.append(empty);detail.replaceChildren();
        status.textContent=text('连线表示同一轮对话涉及的信息','Connections indicate information involved in the same turn');return;
      }
      const layout=positions(graph.nodes.length);canvas.style.height=layout.height+'px';
      const lines=svg('svg',{viewBox:'0 0 340 '+layout.height,preserveAspectRatio:'none','aria-hidden':'true'});lines.classList.add('ontology-links');
      const points=new Map(graph.nodes.map((node,index)=>[node.key,layout.points[index]]));
      for(const edge of graph.edges){
        const a=points.get(edge.from),b=points.get(edge.to);if(!a||!b)continue;
        lines.append(svg('path',{d:`M ${a.x} ${a.y} C ${a.x} ${(a.y+b.y)/2} ${b.x} ${(a.y+b.y)/2} ${b.x} ${b.y}`,fill:'none',stroke:'#c7d2e1','stroke-width':1.6}));
        const x=(a.x+b.x)/2,y=(a.y+b.y)/2;
        lines.append(svg('rect',{x:x-17,y:y-9,width:34,height:18,rx:9,fill:'#f4f7fc'}));
        const label=svg('text',{x,y:y+3,'text-anchor':'middle',fill:'#8290a5','font-size':9});label.textContent=text('关联','link');lines.append(label);
      }
      canvas.append(lines);
      graph.nodes.forEach((node,index)=>{
        const point=layout.points[index],button=el('button',undefined,'ontology-node');button.type='button';button.style.left=(point.x/340*100)+'%';button.style.top=point.y+'px';button.style.setProperty('--node-color',COLORS[node.type]);
        button.setAttribute('aria-label',typeLabel(node.type)+' · '+node.label+' · '+text('定位关联提问','Locate related question'));button.setAttribute('aria-pressed',String(node.key===selected));button.dataset.nodeKey=node.key;
        button.append(icon(node.type),el('span',typeLabel(node.type),'ontology-node-type'),el('b',node.label),el('small',node.id));
        button.title=node.description;
        button.onclick=()=>{selected=node.key;canvas.querySelectorAll('.ontology-node').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));showDetail(node);jump(node.sources.at(-1));};
        canvas.append(button);
      });
      for(const type of new Set(graph.nodes.map(node=>node.type))){const item=el('span',typeLabel(type));item.style.setProperty('--node-color',COLORS[type]);legend.append(item);}
      showDetail(graph.nodes.find(node=>node.key===selected));
      status.textContent=text(graph.nodes.length+' 项信息 · 连线表示同轮关联',graph.nodes.length+' items · Connections link information from the same turn');
    }
    function commit(data){
      if(!lastMessage)return;
      const turn=Number(data.turn_count||data.followups?.ontology?.revision);if(!Number.isInteger(turn)||turn<1)return;
      if(records.length&&turn<=records.at(-1).turn)records=[];
      const record={turn,messageId:lastMessage.id,message:lastMessage.textContent.slice(0,100),...normalize(data)};
      lastMessage.dataset.graphTurn=turn;records.push(record);selected=null;save();render();
    }
    function restore(snapshot){
      const users=[...log.querySelectorAll('.msg.user')];
      if(!users.length){records=[];save();render();return;}
      try{
        const saved=JSON.parse(storage?.getItem(key)||'null');
        records=Array.isArray(saved?.records)?saved.records.filter(record=>Number.isInteger(record.turn)&&record.turn>0&&record.turn<=users.length&&record.message===users[record.turn-1].textContent.slice(0,100)&&Array.isArray(record.nodes)&&Array.isArray(record.edges)):[];
      }catch{records=[];}
      if(!records.length){
        let turn=0;
        for(const entry of snapshot.transcript||[]){
          if(entry.role==='user'){turn++;continue;}
          if(entry.role!=='assistant'||!users[turn-1])continue;
          const data={...entry,turn_count:turn};
          if(turn===users.length){data.followups=snapshot.followups;data.order_snapshot=snapshot.order_snapshot;}
          records.push({turn,message:users[turn-1].textContent.slice(0,100),...normalize(data)});
        }
      }
      for(const record of records){record.messageId=users[record.turn-1].id;users[record.turn-1].dataset.graphTurn=record.turn;}
      save();render();
    }
    reset(sessionId);
    return {registerMessage,commit,restore,reset,setLanguage(value){language=value;render();}};
  }
  const api={normalize,combine,positions,mount};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.OntoConversationGraph=api;
})(typeof window==='undefined'?this:window);
