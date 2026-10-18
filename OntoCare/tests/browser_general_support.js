async page=>{
 await page.goto('http://127.0.0.1:5088/');
 await page.evaluate(()=>sessionStorage.removeItem('ontocare_session'));await page.reload();
 await page.locator('#in').fill('我的 715 充电器无法为我的手机充电');
 await page.locator('#in').press('Enter');
 await page.locator('#log .msg.bot').filter({hasText:'5 分钟'}).waitFor({timeout:10000});
 const quick=await page.locator('#quickReplies').innerText();
 if(quick.includes('订单'))throw Error('Still asking for order');
 if(!quick.includes('充电很慢'))throw Error('Missing charger questions');
 const cite=page.locator('#log .citations').last();
 if(!(await cite.innerText()).includes('Anker 官方'))throw Error('Missing official citation');
 await page.locator('#quickReplies').getByRole('button',{name:'这些方法试过了，还是不行',exact:true}).click();
 await page.locator('#log .msg.bot').filter({hasText:'通用排查后仍未恢复'}).waitFor({timeout:10000});
 await page.screenshot({path:'output/playwright/充电器通用支持.png',fullPage:false});
 return {chargerReply:true,officialCitation:true,noOrderPrompt:true,followup:true};
}
