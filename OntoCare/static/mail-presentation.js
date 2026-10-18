/* Presentation only: keep the original cited text for existing AI edit requests. */
(function(root){
  function project(raw, count){
    raw=String(raw||'');let clean='',cursor=0;const marks=[];
    for(const match of raw.matchAll(/ ?\[(\d+(?:\s*[,，]\s*\d+)*)\]/g)){
      const ids=match[1].split(/[,，]/).map(Number);
      if(!ids.every(id=>id>=1&&id<=count))continue;
      clean+=raw.slice(cursor,match.index);
      marks.push({offset:clean.length,start:match.index,end:match.index+match[0].length,token:match[0]});
      cursor=match.index+match[0].length;
    }
    return {raw,clean:clean+raw.slice(cursor),marks};
  }
  function offset(view,position,after){
    return position+view.marks.filter(mark=>mark.offset<position||(after&&mark.offset===position))
      .reduce((sum,mark)=>sum+mark.end-mark.start,0);
  }
  function applyEdit(view,next,count){
    if(next===view.clean)return view;
    let first=0,last=0;
    while(first<view.clean.length&&first<next.length&&view.clean[first]===next[first])first++;
    while(last<view.clean.length-first&&last<next.length-first&&view.clean.at(-1-last)===next.at(-1-last))last++;
    const start=offset(view,first,false),end=offset(view,view.clean.length-last,true);
    const retained=view.marks.filter(mark=>mark.start>=start&&mark.end<=end).map(mark=>mark.token).join('');
    const raw=view.raw.slice(0,start)+next.slice(first,next.length-last)+retained+view.raw.slice(end);
    return project(raw,count);
  }
  function create(textarea){
    let count=0,view=project('',0);
    function readRaw(){view=applyEdit(view,textarea.value,count);return view.raw;}
    return {
      references(items){count=Array.isArray(items)?items.length:0;},
      write(raw){view=project(raw,count);textarea.value=view.clean;},
      readRaw,
      rawRange(span){readRaw();return [offset(view,span[0],true),offset(view,span[1],true)];},
      clear(){count=0;view=project('',0);textarea.value='';}
    };
  }
  const api={project,applyEdit,offset,create};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.MailPresentation=api;
})(typeof window==='undefined'?this:window);
