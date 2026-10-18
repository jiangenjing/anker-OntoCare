async (page) => {
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width:1440,height:1000});
  await page.goto('http://127.0.0.1:5088/benchmark.html');
  await page.waitForSelector('#cases tr');
  const result={title:await page.title(),tabs:{},errors};
  result.trialCount=await page.locator('#runStatus').innerText();
  result.stats=await page.locator('#stats').innerText();
  await page.screenshot({path:'benchmark/评测主报告.png',fullPage:false});
  for(const tab of ['主报告','可视化看板','稳定性看板','产品化看板']){
    await page.getByRole('tab',{name:tab,exact:true}).click();
    result.tabs[tab]=await page.locator('.section.active').getAttribute('id');
  }
  await page.getByRole('tab',{name:'可视化看板',exact:true}).click();
  await page.screenshot({path:'benchmark/评测可视化.png',fullPage:true});
  result.chartCount=await page.locator('canvas').count();
  await page.getByRole('tab',{name:'稳定性看板',exact:true}).click();
  await page.locator('#faultTable button').first().click();
  result.drawerHasSource=await page.locator('#drawerBody').innerText().then(t=>t.includes('订单信息')&&t.includes('degraded_reason'));
  await page.getByRole('button',{name:'关闭证据',exact:true}).click();
  await page.screenshot({path:'benchmark/评测稳定性.png',fullPage:true});
  await page.getByRole('tab',{name:'主报告',exact:true}).click();
  await page.locator('#group').selectOption('T4');
  result.disambiguationRows=await page.locator('#cases tr').count();
  await page.locator('#mode').selectOption('offline');
  result.offlineStats=await page.locator('#stats').innerText();
  await page.locator('#mode').selectOption('online');
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'导出页面证据 JSON'}).click()]);
  result.download=download.suggestedFilename();
  await page.getByRole('button',{name:'5 分钟答辩路线'}).click();
  result.tour=await page.locator('#drawerBody').innerText().then(t=>t.includes('4:30–5:00'));
  await page.getByRole('button',{name:'关闭证据',exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  result.mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  await page.screenshot({path:'benchmark/评测移动端.png',fullPage:false});
  await page.setViewportSize({width:1440,height:1000});
  await page.route('**/echarts*.js',route=>route.abort());
  await page.reload();
  result.fallbackTables=await page.locator('#groupTable tr').count();
  result.fallbackFlag=await page.locator('body').evaluate(el=>el.classList.contains('no-charts'));
  await page.unroute('**/echarts*.js');await page.reload();
  return result;
}
