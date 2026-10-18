'use strict';
/* Capture locally; only a normal stop sends audio for transcription. Cancel never sends. */
const OntoVoice=(()=>{
  function wav(samples,rate=16000){
    const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
    const text=(offset,value)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
    text(0,'RIFF');view.setUint32(4,36+samples.length*2,true);text(8,'WAVE');text(12,'fmt ');
    view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
    view.setUint32(24,rate,true);view.setUint32(28,rate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);
    text(36,'data');view.setUint32(40,samples.length*2,true);
    for(let i=0;i<samples.length;i++){const n=Math.max(-1,Math.min(1,samples[i]));view.setInt16(44+i*2,n<0?n*32768:n*32767,true);}
    return buffer;
  }
  async function normalize(blob,env){
    const Audio=env.AudioContext||env.webkitAudioContext,Offline=env.OfflineAudioContext||env.webkitOfflineAudioContext;
    if(!Audio||!Offline)throw new Error('当前浏览器无法转换录音格式，请通过“更多”上传 WAV 音频。');
    const context=new Audio();
    try{
      const decoded=await context.decodeAudioData(await blob.arrayBuffer());
      if(decoded.duration<.8)throw new Error('录音太短，请说一句完整的话（约 2–5 秒）后再结束。');
      const offline=new Offline(1,Math.ceil(decoded.duration*16000),16000),source=offline.createBufferSource();
      source.buffer=decoded;source.connect(offline.destination);source.start();
      const audio=await offline.startRendering(),samples=audio.getChannelData(0);
      let peak=0;for(let i=0;i<samples.length;i++)peak=Math.max(peak,Math.abs(samples[i]));
      if(peak<.0001)throw new Error('这段录音几乎没有声音，请检查麦克风是否静音，再说一句完整的话。');
      return new env.Blob([wav(samples)],{type:'audio/wav'});
    }finally{await context.close();}
  }
  function create({env=globalThis,transcribe,onText,onState,convert=normalize}){
    let state={status:'idle',seconds:0,error:''},generation=0,stream,recorder,timer,clock,started;
    const update=values=>{state={...state,...values};onState({...state});};
    const release=()=>{env.clearTimeout(timer);env.clearInterval(clock);stream?.getTracks().forEach(t=>t.stop());stream=null;};
    const cancel=()=>{generation++;if(recorder&&recorder.state!=='inactive')recorder.stop();release();update({status:'idle',seconds:0,error:''});};
    async function start(){
      if(['requesting','recording','transcribing'].includes(state.status))return;
      if(!env.navigator?.mediaDevices?.getUserMedia||!env.MediaRecorder||env.isSecureContext===false){update({status:'error',error:'当前页面无法使用麦克风。请使用 HTTPS / 本机地址，或在“更多”中上传音频。'});return;}
      const token=++generation;update({status:'requesting',seconds:0,error:''});
      try{
        const acquired=await env.navigator.mediaDevices.getUserMedia({audio:true});
        if(token!==generation){acquired.getTracks().forEach(t=>t.stop());return;}
        stream=acquired;
        const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(m=>env.MediaRecorder.isTypeSupported?.(m));
        recorder=mime?new env.MediaRecorder(stream,{mimeType:mime}):new env.MediaRecorder(stream);
        const current=recorder,chunks=[];
        current.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
        current.onerror=()=>{if(token!==generation)return;cancel();update({status:'error',error:'录音中断，请检查麦克风后重试。'});};
        current.onstop=async()=>{
          if(token!==generation)return;release();
          update({status:'transcribing'});
          try{
            const blob=new env.Blob(chunks,{type:current.mimeType||'audio/webm'});
            if(!blob.size)throw new Error('没有录到音频，请检查麦克风后重试。');
            const audio=await convert(blob,env);if(token!==generation)return;
            const text=await transcribe(audio);if(token!==generation)return;
            if(typeof text!=='string'||!text.trim())throw new Error('没有识别到文字，请重新说一句。');
            onText(text.trim());update({status:'idle',seconds:0,error:''});
          }catch(e){if(token===generation)update({status:'error',error:e.message||'转写未完成，请重试。'});}
        };
        current.start();started=Date.now();update({status:'recording'});
        clock=env.setInterval(()=>update({seconds:Math.floor((Date.now()-started)/1000)}),1000);
        timer=env.setTimeout(stop,45000);
      }catch(e){
        if(token!==generation)return;release();
        update({status:'error',error:({NotAllowedError:'未获得麦克风权限，请在浏览器中允许当前页面使用麦克风后重试。',NotFoundError:'没有找到可用麦克风，请连接设备后重试。',NotReadableError:'麦克风被占用或无法读取，请关闭其他录音应用后重试。'})[e.name]||'无法启动录音，请检查麦克风权限。'});
      }
    }
    function stop(){if(recorder?.state==='recording')recorder.stop();}
    return {start,stop,cancel,get state(){return {...state};}};
  }
  return {create,wav,normalize};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=OntoVoice;

// Video frame sampling from the handoff package; silent samples only.
  async function frames(file){
    const url=URL.createObjectURL(file),video=document.createElement('video');video.muted=true;video.preload='auto';video.src=url;
    const once=(name,action)=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>{cleanup();reject(new Error('视频读取超时，请尝试MP4格式。'));},15000);const cleanup=()=>{clearTimeout(timer);video.removeEventListener(name,ok);video.removeEventListener('error',fail);};const ok=()=>{cleanup();resolve();};const fail=()=>{cleanup();reject(new Error('浏览器无法解码此视频。'));};video.addEventListener(name,ok,{once:true});video.addEventListener('error',fail,{once:true});if(action)action();});
    try{await once('loadedmetadata');if(!Number.isFinite(video.duration)||video.duration<=0)throw new Error('视频时长无效。');const canvas=document.createElement('canvas'),scale=Math.min(1,1280/video.videoWidth);canvas.width=Math.max(1,Math.round(video.videoWidth*scale));canvas.height=Math.max(1,Math.round(video.videoHeight*scale));const context=canvas.getContext('2d'),output=[];
      for(let i=0;i<6;i++){const time=Math.min(video.duration-.03,Math.max(.01,video.duration*(i+.1)/6));await once('seeked',()=>{video.currentTime=time;});context.drawImage(video,0,0,canvas.width,canvas.height);output.push({name:file.name,time:Math.round(time*10)/10,data_url:canvas.toDataURL('image/jpeg',.82)});}return output;
    }finally{video.removeAttribute('src');video.load();URL.revokeObjectURL(url);}
  }

if(typeof window!=='undefined')window.OntoMedia={frames};
