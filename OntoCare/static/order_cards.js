/* Use textContent for every source value, including product names and addresses. */
function orderElement(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function orderValue(value){return value===null||value===undefined||value===''?(lang==='en'?'Not provided':'未提供'):String(value);}
function orderCardView(snapshot,interactive){
 const en=lang==='en',root=orderElement('section',undefined,'order-preview');
 const heading=orderElement('div',undefined,'order-preview-heading');heading.append(orderElement('span','📦','order-illustration'),orderElement('div',(interactive?(en?'Is this the order you mean?':'你要查询的是这笔订单吗？'):(en?'Order details':'订单资料明细'))+'\n'+snapshot.order_id));root.append(heading,orderElement('p',en?'Source snapshot · Not live tracking · Ownership not verified':'源表快照 · 非实时物流 · 订单归属尚未核验','order-note'));
 for(const item of [...snapshot.items].sort((a,b)=>String(b.fields['购买日期']||'').localeCompare(String(a.fields['购买日期']||'')))){const f=item.fields,box=orderElement('article',undefined,'order-item');
 box.append(productPicture(item.image,orderValue(f['Product Description'])));
 box.append(orderElement('div',orderValue(f['Product Description']),'order-product-name'),orderElement('div','SKU '+orderValue(f.SKU),'order-sku'));
 const grid=orderElement('div',undefined,'order-fields');
 const labels=en?['Quantity','Amount (source value)','Order status','Tracking status']:['数量','金额（源表数值）','订单状态','物流状态'];
 ['QTY','订单金额','订单状态','物流状态'].forEach((key,i)=>{const cell=orderElement('div');cell.append(orderElement('span',labels[i]),orderElement('b',orderValue(f[key])));grid.append(cell);});box.append(grid);
 const detail=orderElement('details');detail.append(orderElement('summary',en?'Purchase, warranty and shipping details':'查看购买、质保及物流详情'));
 const translations={'No.':'Source No.','购买日期':'Purchase date','质保结束日期':'Warranty end','物流承运商':'Carrier','物流单号':'Tracking number','发货日期':'Ship date','订单地址':'Order address (as provided)'};
 for(const key of ['No.','购买日期','质保结束日期','物流承运商','物流单号','发货日期','订单地址']){const row=orderElement('div',undefined,'order-detail-row');row.append(orderElement('span',en?translations[key]:key),orderElement('div',orderValue(f[key])));detail.append(row);}
 const a=orderElement('a',(en?'Source: order sheet row ':'来源：订单信息第 ')+item.source_row+(en?'':' 行'));a.href=item.source_url;a.target='_blank';a.rel='noopener';detail.append(a);box.append(detail);
 if(interactive&&snapshot.items.length>1&&f.SKU){const button=orderElement('button',en?'Ask about this item':'查询这件商品','quick-choice');button.onclick=()=>{if(sending)return;document.getElementById('in').value=en?`I want to ask about order ${snapshot.order_id}, SKU ${f.SKU}`:`我要查询订单 ${snapshot.order_id} 中的商品 SKU ${f.SKU}`;send();};box.append(button);}root.append(box);}
 if(interactive){const actions=orderElement('div',undefined,'order-confirm-actions'),status=orderElement('div',undefined,'order-note');
 const yes=orderElement('button',en?'Yes, this order':'是这笔订单','quick-choice');yes.onclick=()=>{if(sending)return;status.textContent=en?'Selected for this conversation; ownership is not verified.':'已选为本次咨询订单；不代表订单归属已核验。';document.getElementById('in').value=en?`Yes, I am asking about order ${snapshot.order_id}`:`是这笔订单，我要查询 ${snapshot.order_id}`;send();};
 const change=orderElement('button',en?'Use another order':'换一笔订单','quick-choice');change.onclick=()=>{if(sending)return;const input=document.getElementById('in');input.value='';input.placeholder=en?'Enter the other order number':'请输入另一笔订单号';input.focus();status.textContent=en?'Enter another order number to switch.':'输入另一笔订单号后切换，本卡片保留为历史记录。';};actions.append(yes,change);root.append(actions,status);}
 return root;
}
function showOrderCard(snapshot){const log=document.getElementById('log'),card=orderCardView(snapshot,true);log.append(card);card.scrollIntoView({block:'nearest'});}
function renderOrderDetails(snapshot){const box=document.getElementById('orderDetailsPanel');box.replaceChildren();if(snapshot)box.append(orderCardView(snapshot,false));}
