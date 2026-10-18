async (page) => {
 await page.reload();
 const results=[];
 async function ask(text,expected){
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/chat/stream')&&r.request().method()==='POST',{timeout:90000});
  await page.locator('#in').fill(text);
  await page.locator('button.send').click();
  const response=await responsePromise;
  const events=(await response.text()).trim().split('\n').map(JSON.parse);
  const result=events.find(e=>e.type==='result').data;
  await page.locator('button.send:not([disabled])').waitFor({timeout:90000});
  if(result.response_language!==expected)throw Error('Response language: '+text);
  if(await page.locator('html').getAttribute('lang')!==expected)throw Error('UI language: '+text);
  const questions=await page.locator('#followupQuestions button').allTextContents();
  const quick=await page.locator('#quickReplies button').allTextContents();
  for(const q of [...questions,...quick]){
   if(expected==='en'&&/[\u4e00-\u9fff]/.test(q))throw Error('Chinese option after English: '+q);
   if(expected==='zh'&&!/[\u4e00-\u9fff]/.test(q))throw Error('Non-Chinese option: '+q);
  }
  if(expected==='en'&&/[\u4e00-\u9fff]/.test(result.reply))throw Error('Chinese reply to English');
  if(expected==='zh'&&!/[\u4e00-\u9fff]/.test(result.reply))throw Error('Non-Chinese reply');
  results.push({input:text,language:result.response_language,model_status:result.model_status,route:result.trace.answer_route,questions,quick,citations:result.citations.map(c=>c.id)});
 }
 await ask('T2080 EB1L 加水异常，应该怎么办？','zh');
 await ask('Please explain step 1.','en');
 await page.screenshot({path:'output/playwright/会话语言-英文.png'});
 await ask('T2080','en');
 await ask('这一步怎么做？请用简单的话解释。','zh');
 await page.screenshot({path:'output/playwright/会话语言-中文.png'});
 await page.reload();
 await page.locator('#log .msg.user').first().waitFor();
 if(await page.locator('html').getAttribute('lang')!=='zh')throw Error('Restored wrong language');
 return {passed:true,turns:results};
}
