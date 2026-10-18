'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {create,wav,normalize}=require('../static/multimodal-media.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(overrides={},hooks={}){
  const tracks={stopped:0,getTracks(){return [{stop:()=>this.stopped++}];}};
  const recordings=[];
  class Recorder {
    static isTypeSupported(){return true;}
    constructor(){this.state='inactive';this.mimeType='audio/webm';recordings.push(this);}
    start(){this.state='recording';}
    stop(){this.state='inactive';setImmediate(()=>{this.ondataavailable({data:new Blob(['fixture'])});this.onstop();});}
  }
  const timeouts=[],intervals=[];
  const env={navigator:{mediaDevices:{getUserMedia:async()=>tracks}},MediaRecorder:Recorder,Blob,isSecureContext:true,
    setTimeout:fn=>{timeouts.push(fn);return timeouts.length;},clearTimeout(){},setInterval:fn=>{intervals.push(fn);return intervals.length;},clearInterval(){},...overrides};
  const states=[],texts=[],calls=[];
  const controller=create({env,onState:s=>states.push(s),onText:t=>texts.push(t),convert:async()=>new Blob([wav(new Float32Array(16000))],{type:'audio/wav'}),transcribe:async audio=>{calls.push(audio);return hooks.transcribe?hooks.transcribe(audio):'我的设备吸力弱';}});
  return {controller,env,tracks,recordings,states,texts,calls,timeouts};
}
test('WAV header, signed PCM, clipping and length are valid',()=>{
  const buffer=wav(new Float32Array([-2,-.5,0,.5,2])),v=new DataView(buffer);
  assert.equal(Buffer.from(buffer).subarray(0,4).toString(),'RIFF');
  assert.equal(Buffer.from(buffer).subarray(8,12).toString(),'WAVE');
  assert.equal(v.getUint32(24,true),16000);assert.equal(v.getUint16(22,true),1);
  assert.equal(v.getUint32(40,true),10);assert.equal(buffer.byteLength,54);
  assert.equal(v.getInt16(44,true),-32768);assert.equal(v.getInt16(52,true),32767);
});
test('microphone records first, normal stop transcribes WAV then releases tracks',async()=>{
  const f=fixture();await f.controller.start();assert.equal(f.controller.state.status,'recording');assert.equal(f.calls.length,0);
  f.controller.stop();await tick();await tick();
  assert.equal(f.tracks.stopped,1);assert.equal(f.calls.length,1);assert.equal(f.calls[0].type,'audio/wav');
  assert.deepEqual(f.texts,['我的设备吸力弱']);assert.equal(f.controller.state.status,'idle');
});
test('cancel during recording discards audio without a network call',async()=>{
  const f=fixture();await f.controller.start();f.controller.cancel();await tick();
  assert.equal(f.tracks.stopped,1);assert.equal(f.calls.length,0);assert.equal(f.controller.state.status,'idle');
});
test('permission denied reports a clear error without opening a file picker',async()=>{
  const error=Object.assign(new Error('denied'),{name:'NotAllowedError'});
  const f=fixture({navigator:{mediaDevices:{getUserMedia:async()=>{throw error;}}}});
  await f.controller.start();assert.equal(f.controller.state.status,'error');assert.match(f.controller.state.error,/权限/);assert.equal(f.calls.length,0);
});
test('cancel while permission is pending releases eventual stream and does not start recording',async()=>{
  let grant;const f=fixture({navigator:{mediaDevices:{getUserMedia:()=>new Promise(resolve=>grant=resolve)}}});
  const start=f.controller.start();f.controller.cancel();grant(f.tracks);await start;
  assert.equal(f.tracks.stopped,1);assert.equal(f.recordings.length,0);assert.equal(f.calls.length,0);
});
test('late stop from a cancelled recording cannot close a new recording stream',async()=>{
  const f=fixture();await f.controller.start();f.controller.cancel();await f.controller.start();await tick();
  assert.equal(f.controller.state.status,'recording');assert.equal(f.tracks.stopped,1);
  f.controller.cancel();await tick();assert.equal(f.tracks.stopped,2);assert.equal(f.calls.length,0);
});
test('double click while permission is pending cannot create two recordings',async()=>{
  let grant;const f=fixture({navigator:{mediaDevices:{getUserMedia:()=>new Promise(resolve=>grant=resolve)}}});
  const start=f.controller.start();await f.controller.start();grant(f.tracks);await start;
  assert.equal(f.recordings.length,1);f.controller.cancel();await tick();
});
test('automatic duration limit stops capture and transcribes once',async()=>{
  const f=fixture();await f.controller.start();f.timeouts[0]();await tick();await tick();assert.equal(f.calls.length,1);assert.equal(f.tracks.stopped,1);
});
test('missing recorder is an explicit unsupported error without network access',async()=>{
  const f=fixture({MediaRecorder:undefined});await f.controller.start();assert.equal(f.controller.state.status,'error');assert.equal(f.calls.length,0);
});
test('ASR failure releases capture and leaves the draft callback untouched',async()=>{
  const f=fixture({},{transcribe:async()=>{throw new Error('语音服务暂不可用');}});
  await f.controller.start();f.controller.stop();await tick();await tick();
  assert.equal(f.controller.state.status,'error');assert.equal(f.tracks.stopped,1);assert.equal(f.texts.length,0);
  assert.match(f.controller.state.error,/暂不可用/);
});
test('empty ASR output is not presented as a successful transcription',async()=>{
  const f=fixture({},{transcribe:async()=>''});await f.controller.start();f.controller.stop();await tick();await tick();
  assert.equal(f.controller.state.status,'error');assert.equal(f.texts.length,0);
});
test('cancel during ASR ignores its late result rather than writing into another case',async()=>{
  let complete;const f=fixture({},{transcribe:()=>new Promise(resolve=>complete=resolve)});
  await f.controller.start();f.controller.stop();await tick();await tick();
  assert.equal(f.controller.state.status,'transcribing');f.controller.cancel();complete('迟到的文字');await tick();
  assert.equal(f.controller.state.status,'idle');assert.equal(f.texts.length,0);
});
function decoderFixture(duration=1,amplitude=.01){
  let closed=0;
  class Audio {async decodeAudioData(){return {duration};}async close(){closed++;}}
  class Offline {createBufferSource(){return {connect(){},start(){}};}async startRendering(){return {getChannelData:()=>new Float32Array(Math.ceil(duration*16000)).fill(amplitude)};}}
  return {env:{AudioContext:Audio,OfflineAudioContext:Offline,Blob},closed:()=>closed};
}
test('nearly silent recordings are rejected locally before calling ASR',async()=>{
  const f=decoderFixture(1,0);await assert.rejects(normalize(new Blob(['fixture']),f.env),/没有声音/);assert.equal(f.closed(),1);
});
test('very short recordings give actionable guidance and close the audio context',async()=>{
  const f=decoderFixture(.4,.05);await assert.rejects(normalize(new Blob(['fixture']),f.env),/录音太短/);assert.equal(f.closed(),1);
});
test('quiet but non-silent audio remains eligible and produces a WAV',async()=>{
  const f=decoderFixture(1,.0003);const audio=await normalize(new Blob(['fixture']),f.env);assert.equal(audio.type,'audio/wav');assert.equal(audio.size,32044);assert.equal(f.closed(),1);
});
