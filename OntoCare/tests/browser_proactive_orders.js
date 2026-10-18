async page=>{
 await page.goto('http://127.0.0.1:5088/');
 await page.evaluate(()=>sessionStorage.removeItem('ontocare_session'));await page.reload();
 await page.locator('#in').fill('我的产品是吸奶器 T8D04');await page.locator('#in').press('Enter');
 const panel=page.locator('.selection-panel').last();await panel.getByRole('button',{name:'分析这笔订单',exact:true}).first().waitFor({timeout:60000});
 const text=await panel.innerText();if(!text.includes('T8D04')||!text.includes('演示数据'))throw Error('Incorrect candidates or missing scope');
 await page.locator('#in').fill('Anker002这个是订单号啊');await page.locator('#in').press('Enter');
 await page.waitForFunction(()=>!sending);await page.getByText(/不匹配，我重新帮您匹配/).last().waitFor();
 const latest=page.locator('.selection-panel').last();const count=await latest.getByRole('button',{name:'分析这笔订单',exact:true}).count();
 await latest.getByRole('button',{name:'分析这笔订单',exact:true}).first().click();await page.waitForFunction(()=>!sending,{timeout:60000});
 const result=await page.evaluate(async()=>{const r=await fetch('/api/session/'+sid);return r.json()});
 if(!result.order_snapshot?.items.some(i=>String(i.fields.SKU).startsWith('T8D04')))throw Error('Click failed to select breast pump order');
 if(result.order_snapshot.ownership_verified)throw Error('Click incorrectly verifies ownership');
 return {candidateCount:count,selectedOrder:result.order_snapshot.order_id,ownershipVerified:false};
}
