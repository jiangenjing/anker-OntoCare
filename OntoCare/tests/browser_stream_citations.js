async page=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5099/');
 // Simulated delayed transport isolates the rendering behavior from model timing.
 await page.evaluate(()=>{
   const original=window.fetch;
   window.fetch=(url,options)=>{
     if(url!=='/api/chat/stream')return original(url,options);
     const progress={type:'progress',language:'zh',text:'查询服务定义',citations:[{type:'ServiceOntology',label:'服务定义',uri:'/ontology-references.html#service-case',detail:'服务案件关联订单、产品与知识；这是定义引用。'}]};
     return Promise.resolve(new Response(new ReadableStream({start(controller){
       const enc=new TextEncoder();controller.enqueue(enc.encode(JSON.stringify(progress)+'\n'));
       window.finishCitationStream=()=>{controller.enqueue(enc.encode(JSON.stringify({type:'result',status:200,data:{reply:'这是界面验证回复。',citations:[],trace:{},turn_count:1,response_language:'zh'}})+'\n'));controller.close()};
     }}),{headers:{'Content-Type':'application/x-ndjson'}}));
   };
 });
 await page.getByRole('textbox',{name:'输入你的问题…'}).fill('界面引用验证');
 await page.getByRole('button',{name:'发送',exact:true}).click();
 const citation=page.getByRole('button',{name:'[Service Ontology: 服务定义]',exact:true});
 await citation.waitFor();await citation.hover();
 if(!(await citation.getAttribute('title')).includes('定义引用'))throw Error('Missing hover details');
 if(!await page.locator('.process').evaluate(e=>e.open))throw Error('Stream collapsed before result');
 await citation.click();
 if(!await page.getByText('服务案件关联订单、产品与知识；这是定义引用。',{exact:true}).isVisible())throw Error('No click expansion');
 if(!await page.getByRole('link',{name:'查看本体来源'}).isVisible())throw Error('No source link');
 await page.screenshot({path:'output/playwright/流式步骤引用-展开.png',fullPage:true});
 await page.evaluate(()=>window.finishCitationStream());
 await page.locator('.process.complete').waitFor();
 if(!await page.locator('.process').evaluate(e=>e.open))throw Error('Summary collapsed on completion');
 if(!await page.locator('.process + .msg.bot').isVisible())throw Error('Answer not adjacent to summary');
 await page.locator('.process > summary').click();
 if(await citation.isVisible())throw Error('Manual collapse failed');
 await page.locator('.process > summary').click();
 if(!await citation.isVisible())throw Error('Citation lost after completion');
 const malformed=await page.evaluate(()=>{
   const c=document.createElement('div');
   appendProcessingStep(c,{text:'No references'});
   appendProcessingStep(c,{text:'Malformed references',citations:'bad'});
   appendProcessingStep(c,{text:'Untrusted source',citations:[null,{type:'Ontology',label:'<img src=x onerror=alert(1)>',uri:'javascript:alert(1)',detail:'<script>alert(1)</script>'}]});
   return {rows:c.children.length,images:c.querySelectorAll('img,script').length,links:c.querySelectorAll('a').length};
 });
 if(malformed.rows!==3||malformed.images||malformed.links)throw Error('Unsafe or incompatible citation input');
 if(errors.length)throw Error(errors.join(';'));
 return {hover:true,expanded:true,stream_open:true,complete_expanded:true,answer_adjacent:true,source_preserved:true,malformed,page_errors:errors};
}
