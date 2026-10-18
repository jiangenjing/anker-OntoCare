async page=>{
 await page.goto('http://127.0.0.1:5088/');
 const result=await page.evaluate(()=>{
  sending=false;
  const make=(revision,model)=>({questions:[],ontology:{nodes:[{id:model}],revision},quick_replies:[{text:model+' 如何排查？',text_en:'How can I troubleshoot '+model+'?',node_ids:[model],ontology_revision:revision}]});
  lang='zh';renderFollowups(make(1,'T2280'));
  if(!document.querySelector('#quickReplies').textContent.includes('猜你想问'))throw Error('Missing heading');
  renderFollowups(make(2,'T8D04'));
  if(document.querySelector('#quickReplies').textContent.includes('T2280'))throw Error('Stale option');
  const originalSend=send;let submitted='';send=()=>{submitted=document.getElementById('in').value;};
  document.querySelector('.quick-choice').click();send=originalSend;
  if(submitted!=='T8D04 如何排查？')throw Error('Wrong submission');
  lang='en';renderFollowups(make(3,'T8D04'));
  if(!document.querySelector('.quick-choice').textContent.startsWith('How'))throw Error('Wrong language');
  if(document.querySelector('.quick-choice').title!=='T8D04')throw Error('Missing provenance');
  return {updates:true,clickSubmits:true,english:true,provenance:true};
 });
 await page.reload();return result;
}
