async page=>{
 await page.setViewportSize({width:1280,height:900});await page.goto('http://127.0.0.1:5088/');
 await page.evaluate(()=>sessionStorage.removeItem('ontocare_session'));await page.reload();
 await page.getByText('请选择要分析的订单',{exact:true}).waitFor();
 const cards=page.locator('.selection-panel .product-selection-card');const count=await cards.count();
 if(!count)throw Error('No order cards');
 if((await page.locator('.selection-panel').innerText()).includes('确认这是我的设备'))throw Error('Old copy');
 const options=await page.evaluate(async()=>await (await fetch('/api/user-options')).json());
 const dates=options.choices.map(c=>c.date||'');if(dates.join()!==dates.slice().sort().reverse().join())throw Error('Dates not sorted');
 if(options.choices.some(c=>!c.order_id||!c.sku||!c.image))throw Error('Missing card data');
 await page.screenshot({path:'output/playwright/首页订单选择.png',fullPage:true});
 return {orderCards:count,latest:options.choices[0].date,allHaveOrderAndSku:true};
}
