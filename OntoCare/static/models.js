(function(){
const $=id=>document.getElementById("media-"+id);let catalog,output='',outputSource=null,recordingResult=null;
let requestBusy=false,opening=0;
function setWorking(value){requestBusy=value;for(const id of ['run','record','op','model','testConnection','file'])$(id).disabled=value;}
const debugHistory=[];
function debugEntry(d,body){if(!body||body.action)return;const entry={time:new Date().toISOString(),model:catalog?.models.find(m=>m.id===body.model_id)?.model||body.model_id,operation:body.operation,protocol:body.protocol||'openai',status:d.status||'ERROR',duration_ms:d.duration_ms??null,error_code:d.error_code||null,http_status:d.http_status||null,error:d.error||null};debugHistory.unshift(entry);debugHistory.length=Math.min(debugHistory.length,10);$('debugLog').textContent=JSON.stringify(debugHistory,null,2);}
async function api(body){const r=await fetch('/api/models',body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{}).catch(()=>{const d={status:'ERROR',error_code:'LOCAL_NETWORK',error:'无法连接本机服务，请确认服务仍在运行后重试。'};debugEntry(d,body);throw Error(d.error);});let d;try{d=await r.json();}catch{d={status:'ERROR',error_code:'LOCAL_NON_JSON',http_status:r.status,error:'本机服务没有返回 JSON，请检查服务是否启动。'};}debugEntry(d,body);if(!r.ok||d.error_code==='LOCAL_NON_JSON')throw Error(d.error||'请求失败');return d;}
function choices(){const op=$('op').value;const ids={text:['nova','glm','deepseek-pro','qwen','kimi','deepseek-flash'],image:['deepseek-flash','qwen','nova','kimi'],video:['nova'],frames:['deepseek-flash','qwen','nova','kimi'],asr:['asr'],tts:['tts'],imagegen:['seedream']}[op];$('model').replaceChildren(...ids.map(id=>{let m=catalog.models.find(m=>m.id===id);return new Option(m.name,id);}));$('file').hidden=!['image','video','frames','asr','imagegen'].includes(op);$('fileLabel').hidden=$('file').hidden;$('file').accept={image:'image/png,image/jpeg,image/webp',imagegen:'image/png,image/jpeg,image/webp',video:'video/mp4',frames:'video/mp4,video/webm,video/quicktime',asr:'audio/*'}[op]||'';$('file').value='';$('limit').textContent={image:' 图片上限 3 MB',imagegen:' 可选参考图，最大 3 MB；输出仅为示意图',video:' MP4 上限 16 MB；完整视频直传，内容仍需核验',frames:' 视频上限 100 MB；本地取最多六帧，仅分析画面，不含音轨',asr:' 音频上限 8 MB；转为 16 kHz 单声道 WAV，录音最多 45 秒'}[op]||'';$('voiceControls').hidden=op!=='asr';$('framePreview').replaceChildren();voice.cancel();clearResult();modelLabel();}
function modelLabel(){$('modelid').textContent=catalog.models.find(m=>m.id===$('model').value).model;}
const dataURL=blob=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(blob);});
async function wav(file){if(file.size>8*1024*1024)throw Error('音频超过 8 MB。');const audio=await OntoVoice.normalize(file,window);if(audio.size>8*1024*1024)throw Error('转换后音频超过 8 MB，请裁剪。');return audio;}
function clearResult(){output='';outputSource=null;$('copy').hidden=true;$('useDraft').hidden=true;$('result').value='';$('media').replaceChildren();}
function present(d,source){$('status').textContent=`${d.model_name||source.model_id} · ${d.status==='OK'?'调用成功':d.status} · ${d.duration_ms??'未开始'} ms · ${d.error||'本次结果仍需核验'}`;if(d.status!=='OK')return;output=d.text||'';outputSource=source;$('result').value=output;$('copy').hidden=!output;$('useDraft').hidden=!output;if(d.audio_url){const a=document.createElement('audio');a.controls=true;a.src=d.audio_url;$('media').append(a);}for(const url of d.images||[]){const i=document.createElement('img');i.src=url;i.alt='AI 生成示意图';$('media').append(i);}}
const voice=OntoVoice.create({
 transcribe:async blob=>{clearResult();const d=await api({operation:'asr',model_id:'asr',protocol:'openai',file:{name:'recording.wav',data_url:await dataURL(blob)}});if(d.status!=='OK'||!d.text?.trim())throw Error(d.error||'没有识别到文字。');recordingResult=d;return d.text;},
 onText:text=>{present(recordingResult,{model_id:'asr',operation:'asr'});$('prompt').value=text;$('voiceStatus').textContent='转写已填入可编辑草稿，未自动发送给客服。';},
 onState:state=>{const busy=requestBusy||['requesting','recording','transcribing'].includes(state.status);for(const id of ['run','op','model','record','testConnection','file'])$(id).disabled=busy;$('stopRecord').hidden=state.status!=='recording';$('cancelRecord').hidden=!busy;$('voiceStatus').textContent=state.error||(state.status==='recording'?`录音 ${state.seconds} / 45 秒`:state.status==='requesting'?'等待麦克风授权':state.status==='transcribing'?'正在转写，完成后请核对':'');}
});
$('record').onclick=()=>voice.start();$('stopRecord').onclick=()=>voice.stop();$('cancelRecord').onclick=()=>voice.cancel();window.addEventListener('pagehide',()=>voice.cancel());
$('testConnection').onclick=async()=>{if(requestBusy)return;const model_id=$('model').value;if(['asr','tts','seedream'].includes(model_id)){$('status').textContent='该模型请通过实际语音或图片生成任务验证，不支持文字连接测试。';return;}try{setWorking(true);clearResult();$('status').textContent='验证连接中…';const d=await api({operation:'test',model_id,protocol:'openai'});present(d,{operation:'test',model_id});$('useDraft').hidden=true;}catch(e){$('status').textContent=e.message;}finally{setWorking(false);}};
$('op').onchange=choices;$('model').onchange=()=>{clearResult();modelLabel();};

$('run').onclick=async()=>{if(requestBusy)return;setWorking(true);clearResult();$('status').textContent='处理中…';try{const op=$('op').value,body={model_id:$('model').value,operation:op,protocol:'openai',text:$('prompt').value};if(['image','video','frames','asr'].includes(op)||(op==='imagegen'&&$('file').files[0])){let file=$('file').files[0];if(!file)throw Error('请先选择文件。');const max={image:3,imagegen:3,video:16,frames:100,asr:8}[op];if(file.size>max*1024*1024)throw Error('文件超过 '+max+' MB。');if(op==='frames'){body.frames=await OntoMedia.frames(file);$('framePreview').replaceChildren(...body.frames.map(f=>{const figure=document.createElement('figure');figure.style.margin='4px';const img=document.createElement('img');img.src=f.data_url;img.style.width='120px';const caption=document.createElement('figcaption');caption.textContent=f.time+' 秒 · 抽样';figure.append(img,caption);return figure;}));}else{if(op==='asr')file=await wav(file);body.file={name:file.name||'audio.wav',data_url:await dataURL(file)};}}const d=await api(body);present(d,{operation:op,model_id:body.model_id});if(op==='asr'&&d.status==='OK')$('prompt').value=d.text;}catch(e){$('status').textContent=e.message;}finally{setWorking(false);}};
$('useDraft').onclick=()=>{
  const text=$('result').value.trim();if(!text||!outputSource)return;
  if(sending||mediaUploading){$('status').textContent='客服正在处理上一条消息，请稍后再带入。';return;}
  const input=document.getElementById('in');
  const observation=`待核验模型观察（${outputSource.operation} / ${outputSource.model_id}）：\n${text.slice(0,6000)}\n请结合产品型号和知识库核对；不要将观察当作已确认故障。`;
  input.value=[input.value,observation].filter(Boolean).join('\n');
  document.querySelector('.media-notice')?.remove();
  const notice=document.createElement('p');notice.className='media-notice';notice.setAttribute('role','status');notice.textContent='已将多模态文字提交客服 Agent，正在结合型号与知识库分析。';
  input.parentElement.before(notice);dialog.close();input.focus();send();
};
$('copy').onclick=async()=>{output=$('result').value.trim();try{await navigator.clipboard.writeText('以下为模型提取的待核验材料，请结合产品型号与知识库核对：\n'+output);$('status').textContent='已复制，返回客服后粘贴并确认发送。';}catch{$('status').textContent='请手动选择并复制上方文字。';}};
const dialog=document.getElementById('customerMedia');
let ready=null;
function loadCatalog(){
  if(!ready)ready=api().then(d=>{catalog=d.catalog;return d;}).catch(error=>{ready=null;throw error;});
  return ready;
}
async function openMedia(operation){
  dialog.showModal();if(requestBusy)return;const token=++opening;for(const id of ['run','record','op','model','testConnection','file'])$(id).disabled=true;$('status').textContent='正在读取多模态设置…';
  try{
    await loadCatalog();
    // Read the server-owned connection status when opening the assistant.
    const data=await api();if(token!==opening||!dialog.open)return;
    $('configHint').textContent=data.catalog.configured?'演示连接已预置，可直接使用':'后台连接暂不可用，请联系演示人员';
    $('op').value=operation||'image';choices();$('status').textContent='选择输入方式，识别结果可核对后带入当前对话。';
  }catch(error){if(token!==opening||!dialog.open)return;$('status').textContent=error.message;$('run').disabled=true;$('op').disabled=true;}
}
document.querySelectorAll('[data-open-media]').forEach(button=>button.addEventListener('click',()=>openMedia(button.dataset.openMedia)));
document.querySelector('[data-close-media]').addEventListener('click',()=>dialog.close());
dialog.addEventListener('close',()=>{opening++;voice.cancel();});
dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});


})();
