async (page) => {
  const checks=[];
  const check=(condition,name)=>{if(!condition)throw Error(name);checks.push(name)};
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.reload();
  await page.getByRole('heading',{name:'从问题线索，到可核查的行动'}).waitFor();
  check(await page.getByRole('button',{name:'工单总数 63 源表第 2–64 行 查看全部工单 →'}).count()===1,'63 ticket total visible');
  await page.getByRole('button',{name:'RC3 · 产品设计 18 错误码候选，待核查 定义 / 工单 / 规则 →'}).click();
  let dialog=page.getByRole('dialog');
  check(await dialog.getByRole('row').count()===19,'RC3 has exactly 18 candidate rows');
  check((await dialog.innerText()).includes('错误码不是设计缺陷证据'),'RC3 uncertainty explicit');
  check((await dialog.innerText()).includes('知识匹配核查'),'Knowledge binding visible');
  await page.getByRole('button',{name:'关闭详情'}).click();
  await page.getByRole('button',{name:'RC1 · 上下文丢失 0 有证据的候选工单 定义 / 工单 / 规则 →'}).click();
  check((await dialog.innerText()).includes('当前没有可由测评集支持的命中工单'),'RC1 empty-state explains missing evidence');
  await page.getByRole('button',{name:'关闭详情'}).click();
  await page.getByRole('button',{name:'Troubleshooting/Product usage，52 条，查看工单',exact:true}).click();
  const found=[];
  for(let i=0;i<7;i++){
    const labels=await page.locator('#tickets tbody tr td:first-child').allTextContents();
    found.push(...labels.map(x=>Number(x.match(/\d+/)[0])));
    if(i<6)await page.getByRole('button',{name:'下一页',exact:true}).click();
  }
  const expected=Array.from({length:53},(_,i)=>i+12).filter(x=>x!==48);
  check(JSON.stringify(found)===JSON.stringify(expected),'52 scenario drilldown rows match source exactly across 7 pages');
  await page.getByRole('button',{name:'X10 Pro Omni，3 条，查看工单',exact:true}).click();
  check(JSON.stringify(await page.locator('#tickets tbody tr td:first-child').allTextContents())===JSON.stringify(['第 17 行','第 22 行','第 29 行']),'Product drilldown matches 3 source rows');
  await page.getByRole('button',{name:'查看详情',exact:true}).first().click();
  check((await dialog.innerText()).includes('2310'),'Ticket detail carries original error code');
  await page.getByRole('button',{name:'关闭详情'}).click();
  await page.getByRole('button',{name:'填写核查记录',exact:true}).first().click();
  await page.getByRole('button',{name:'保存为已核查',exact:true}).click();
  check(await dialog.isVisible(),'Empty review cannot be marked complete');
  await page.getByRole('textbox',{name:'记录已核对内容、剩余缺口或处理建议；保存不代表执行业务动作。'}).fill('浏览器验证记录：已核对测评集行号与分类；产品详情缺失仍需补齐。');
  await page.getByRole('button',{name:'保存为已核查',exact:true}).click();
  await page.reload();
  check(await page.getByText('2 项待核查',{exact:true}).count()===1,'Review persists after reload');
  await page.getByRole('button',{name:'生成改进报告',exact:true}).click();
  for(const [label,file] of [['下载 JSON','report.json'],['下载 HTML','report.html']]){
    const pending=page.waitForEvent('download');
    await page.getByRole('link',{name:label,exact:true}).click();
    const download=await pending;
    await download.saveAs('output/playwright/'+file);
    check(!(await download.failure()),label+' downloads successfully');
  }
  await page.getByRole('button',{name:'关闭详情'}).click();
  await page.getByText('数据来源与规则说明',{exact:true}).click();
  await page.getByRole('textbox',{name:'搜索长尾策略'}).fill('拆单');
  check((await page.locator('#strategies').innerText()).includes('long-tail-json-L007'),'Long-tail strategy provenance searchable');
  await page.getByText('数据来源与规则说明',{exact:true}).click();
  await page.getByRole('button',{name:'查看全部',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.scrollTo(0,0));
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'390px mobile has no horizontal page overflow');
  await page.screenshot({path:'output/playwright/归因工作台-窄屏.png'});
  await page.setViewportSize({width:1440,height:1000});
  await page.evaluate(()=>{for(const k of Object.keys(localStorage))if(k.startsWith('ontocare-attribution-review-v1:'))localStorage.removeItem(k)});
  await page.reload();
  await page.screenshot({path:'output/playwright/归因工作台-桌面.png',fullPage:true});
  check(errors.length===0,'No JavaScript runtime errors');
  console.log(JSON.stringify({passed:checks.length,checks,errors},null,2));
}
