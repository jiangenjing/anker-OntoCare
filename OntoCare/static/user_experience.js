/* Source-backed image cards, feedback and expandable citations. */
function uxText(zh,en){return lang==='en'?en:zh;}
function productPicture(meta,name){
 const box=orderElement('div',undefined,'product-picture');
 if(meta){const image=orderElement('img');image.src=meta.image;image.alt=name;image.loading='lazy';image.onerror=()=>{box.textContent=uxText('图片暂不可用','Image unavailable');};box.append(image);const source=orderElement('a',uxText('官方系列图','Official product image'));source.href=meta.source;source.target='_blank';source.rel='noopener';source.title=meta.note;box.append(source);}
 else box.append(orderElement('span','📦'),orderElement('small',uxText('暂无已核验图片','No verified image available')));
 return box;
}
function showSelections(items,target){
 if(!items?.length)return;
 const root=orderElement('section',undefined,'selection-panel');root.append(orderElement('b',items[0].kind==='order'?uxText('请选择要分析的订单','Select an order to analyze'):uxText('请选择产品型号继续分析','Select a model to continue')),orderElement('p',uxText('演示数据 · 按源表购买日期由近到远 · 不代表你的个人购买记录','Demo records · Most recent purchase first · These are not your personal orders'),'order-note'));
 const grid=orderElement('div',undefined,'product-selection-grid');
 for(const item of items){const card=orderElement('article',undefined,'product-selection-card');card.append(productPicture(item.image,item.name));const info=orderElement('div',undefined,'selection-card-info');info.append(orderElement('b',item.name),orderElement('p',item.sku?'SKU '+item.sku:'型号 '+item.pn),orderElement('small',uxText('购买日期：','Purchase date: ')+orderValue(item.date)));
 if(item.order_id)info.append(orderElement('p','订单 '+item.order_id));
 const button=orderElement('button',item.kind==='order'?uxText('分析这笔订单','Analyze this order'):uxText('选择此型号继续','Continue with this model'),'quick-choice selection-primary');button.type='button';button.onclick=()=>{if(sending)return;document.getElementById('in').value=lang==='en'?item.message_en:item.message;root.querySelectorAll('button').forEach(b=>b.disabled=true);send();};const actions=orderElement('div',undefined,'selection-card-actions');actions.append(button);
 if(item.source_url){const a=orderElement('a',uxText('查看源表 ↗','View source ↗'),'selection-source');a.href=item.source_url;a.target='_blank';a.rel='noopener';actions.append(a);}info.append(actions);card.append(info);grid.append(card);}
 root.append(grid);
 if(items[0].kind==='order'){const none=orderElement('button',uxText('这些都不是我的订单','None of these are my orders'),'quick-choice');none.onclick=()=>{if(sending)return;document.getElementById('in').value=uxText('这些都不是我的订单','None of these are my orders');root.querySelectorAll('button').forEach(b=>b.disabled=true);send();};root.append(none);}
 (target||document.getElementById('log')).append(root);
}
function showGuide(diagram){
 const dialog=orderElement('dialog',undefined,'guide-dialog'),close=orderElement('button','关闭','quick-choice');close.onclick=()=>dialog.close();const img=orderElement('img');img.src=diagram.url;img.alt=diagram.title;img.onerror=()=>{img.replaceWith(orderElement('p','图片暂时无法加载，请查看下方原文引用。'));};const a=orderElement('a',diagram.source_label);a.href=diagram.source_url;a.target='_blank';a.rel='noopener';dialog.append(close,orderElement('h3',diagram.title),img,a);dialog.addEventListener('close',()=>dialog.remove());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});document.body.append(dialog);dialog.showModal();
}
function showGuides(diagrams){if(!diagrams?.length)return;const bar=orderElement('div',undefined,'feedback-bar');diagrams.forEach((d,i)=>{const b=orderElement('button','查看图示 '+(i+1));b.onclick=()=>showGuide(d);bar.append(b);});document.getElementById('log').append(bar);}
function showFeedback(turn){
 const box=orderElement('div',undefined,'feedback-bar'),status=orderElement('span');status.setAttribute('role','status');
 async function save(rating,detail=''){try{const r=await fetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sid,turn,rating,detail})});if(!r.ok)throw Error();status.textContent=uxText('感谢反馈，已记录在本次会话中。','Thank you. Feedback saved for this conversation.');}catch(e){status.textContent=uxText('反馈未保存，请重试。','Feedback was not saved. Please retry.');}}
 const yes=orderElement('button',uxText('👍 有帮助','👍 Helpful')),no=orderElement('button',uxText('👎 没解决','👎 Not resolved')),human=orderElement('button',uxText('联系人工','Contact support'));yes.onclick=()=>save('helpful');
 no.onclick=()=>{save('unresolved');if(box.querySelector('textarea'))return;const input=orderElement('textarea');input.placeholder=uxText('哪里没帮到你？也可以直接点下面的选项。','What was not helpful? You can also choose an option below.');const submit=orderElement('button',uxText('提交反馈','Submit feedback'));submit.onclick=()=>save('unresolved',input.value);box.append(input,submit);for(const text of (lang==='en'?["I tried it, but it did not work.","That does not answer my question.","I cannot find the part. Please explain where it is."]:['试过了，还是不行','回答的不是我的问题','找不到对应部件，请解释怎么找'])){const b=orderElement('button',text);b.onclick=()=>{if(sending)return;document.getElementById('in').value=text;send();};box.append(b);}};
 human.onclick=()=>{const panel=document.getElementById('handoff');panel.hidden=false;document.getElementById('handoffStatus').textContent=turn>8?uxText('请选择人工或邮件处理。','Choose human support or email.'):uxText('可在超过 8 轮后提交转接；目前可继续补充问题。','Handoff is available after 8 turns. You can continue describing the issue.');panel.scrollIntoView({block:'nearest'});};box.append(yes,no,human,status);document.getElementById('log').append(box);
}
async function expandableCitation(detail,c){
 if(!detail.open||detail.dataset.loaded)return;
 const content=detail.querySelector('.citation-preview');content.textContent='正在读取原文…';
 try{const url=new URL(c.url,location.origin);if(url.origin!==location.origin||!url.pathname.startsWith('/api/sources/'))throw Error();const r=await fetch(url);if(!r.ok)throw Error();const doc=new DOMParser().parseFromString(await r.text(),'text/html');content.textContent=(doc.querySelector('pre')?.textContent||'暂无原文预览').slice(0,1400);detail.dataset.loaded='1';}
 catch(e){content.textContent='无法读取预览，可打开来源查看。';}
}
