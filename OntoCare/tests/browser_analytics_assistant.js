async page=>{
 await page.setViewportSize({width:1440,height:1000});
 await page.goto('http://127.0.0.1:5088/analytics');
 await page.getByRole('button',{name:'AI 经营归因助手',exact:true}).click();
 await page.getByRole('button',{name:'X10 Pro 最近工单为什么多？',exact:true}).click();
 await page.locator('.ops-trace').waitFor({timeout:25000});
 const answer=await page.locator('.ops-message').last().innerText();
 if(!answer.includes('14 条')||!answer.includes('22.2%'))throw Error('Incorrect facts');
 await page.locator('.ops-trace summary').click();
 await page.locator('.ops-node').first().click();
 await page.locator('#overlay.open').waitFor();
 if(!(await page.locator('#drawerBody').innerText()).includes('Excel 第'))throw Error('Missing source rows');
 await page.locator('#close').click();
 await page.screenshot({path:'output/playwright/经营归因助手.png',fullPage:false});
 await page.setViewportSize({width:390,height:844});
 const dimensions=await page.locator('#opsAssistant').boundingBox();
 if(dimensions.width>390||dimensions.height>600)throw Error('Mobile panel overflow');
 await page.getByRole('button',{name:'折叠经营归因助手'}).click();
 if(await page.locator('#opsAssistant').isVisible())throw Error('Collapse failed');
 await page.setViewportSize({width:1440,height:1000});
 return {realReply:answer,evidenceClickable:true,mobile:true,collapse:true};
}
