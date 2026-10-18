async page=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setViewportSize({width:1440,height:1080});
 await page.goto('http://127.0.0.1:5088/benchmark.html#view=principles');await page.reload();
 await page.locator('#archRunMode').selectOption('offline');
 await page.locator('#archRun').click();
 const result=page.locator('#archRunResults button').first();await result.waitFor({timeout:30000});
 const resultLabel=await result.innerText();await result.click();
 await page.locator('#drawerWrap.open').waitFor();
 await page.getByText('逐轮 Trace 时间轴 · 完整原文',{exact:true}).click();
 const body=await page.locator('#drawerBody').innerText();
 if(!body.includes('逐轮 Trace 时间轴')||!body.includes('source_verbatim')||!body.includes('NOT_MEASURED'))throw Error('Trace missing real stages or unmeasured scores');
 const verdictBefore=await page.locator('.trace-verdict').innerText();
 await page.locator('#markTraceFixed').click();
 if(!(await page.locator('#traceMark').innerText()).includes('原成绩不变'))throw Error('Repair annotation unclear');
 if(!(await page.locator('.trace-verdict').innerText()).includes('通过'))throw Error('Unexpected offline result: '+verdictBefore);
 await page.getByRole('button',{name:'查看原始工单',exact:true}).click();
 await page.locator('#traceOriginal').waitFor();
 await page.screenshot({path:'output/playwright/红蓝对抗-真实Trace.png',fullPage:true});
 await page.keyboard.press('Escape');
 await page.locator('#archRed').click();await page.locator('#cases [data-case]').first().click();
 await page.getByText('逐轮 Trace 时间轴 · 完整原文',{exact:true}).click();
 if(!(await page.locator('#drawerBody').innerText()).includes('NOT_MEASURED_PER_TURN'))throw Error('Historical judge scores misrepresented');
 await page.keyboard.press('Escape');
 await page.getByRole('tab',{name:'评测原理',exact:true}).click();
 if(errors.length)throw Error(errors.join(';'));
 return {resultLabel,liveTrace:true,historicalUnmeasured:true,manualMarkDoesNotChangeResult:true,pageErrors:errors};
}
