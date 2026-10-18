/* Presentation-only suggestions. Clicking still uses the existing chat workflow. */
(function(root){
  const q=(text,text_en,label,label_en)=>({text,text_en,label,label_en});
  const demos=[
    q('查询演示订单 Anker002 中 SKU T2080GA1 的商品和物流记录','Show the product and saved tracking records for SKU T2080GA1 in demo order Anker002.','核对订单与包裹','Order & parcels'),
    q('S1 Pro 扫地机 T2080 出现加水错误码 EB1L，应该如何排查？','How can I troubleshoot water-filling error EB1L on the S1 Pro robot vacuum T2080?','S1 Pro 加水报错','S1 Pro water error'),
    q('S1 Pro 吸奶器 T8D04 吸力不足，如何区分原因并检查配件？','How can I narrow down weak suction and check parts on the S1 Pro breast pump T8D04?','吸奶器吸力排查','Pump suction checks')
  ];
  function select(data,{asked=[]}={}){
    if(!data)return [];
    const ontology=data.ontology||{},nodes=ontology.nodes||[];
    if(!Number(ontology.revision)&&!asked.length)return demos.map(item=>({...item}));
    const quick=data.quick_replies||[],questions=data.questions||[],result=[];
    const used=new Set(asked.map(text=>text.trim()));
    function add(item){
      if(!item?.text||used.has(item.text)||used.has(item.text_en)||result.some(q=>q.text===item.text))return;
      result.push({...item});
    }
    const answers=quick.filter(item=>!item.source_ids?.length);
    // Keep all choices when they answer a required clarification or guided step.
    const required=answers.some(item=>/购买渠道|官方店铺|其他平台|退货原因|解决了|还是不行|这一步|型号 T2080|不知道型号/.test(item.text));
    if(required){answers.forEach(add);return result.slice(0,3);}
    const order=nodes.find(node=>node.type==='Order')?.id;
    const product=ontology.product||nodes.find(node=>node.type==='Product')?.id;
    const context=order?'订单 '+order:(product||'当前问题');
    const contextEn=order?'order '+order:(product||'this issue');
    // Avoid three variants of the same shipping query. Cover facts, troubleshooting,
    // and service requirements without claiming that any action has been completed.
    if(ontology.intent==='shipping'&&order){
      add(q('请核对订单 '+order+' 的全部商品、分包裹和物流记录','Please check all items, parcels and saved tracking records for order '+order+'.','核对商品与包裹','Items & parcels'));
      add(q('订单 '+order+' 的物流记录和实际收货不一致，应该如何核查？','How should a difference between saved tracking and actual receipt be reviewed for order '+order+'?','物流与实收不符','Tracking mismatch'));
    }else{
      answers.slice(0,1).forEach(add);
      const evidence=questions.filter(item=>item.source_ids?.some(id=>id!=='service-rules'));
      if(evidence.length){
        const item=evidence.find(item=>/第\d+步|错误码|排查/.test(item.text))||evidence[0];
        add({...item,text:item.text.replace(/（资料 [^）]+）/g,''),label:item.text.replace(/（资料 [^）]+）/g,'')});
      }
    }
    add(q(context+'：申请售后核查需要准备哪些购买凭证和故障资料？','What proof of purchase and issue details are needed for a service review of '+contextEn+'?','售后需要哪些凭证','Service documents'));
    questions.forEach(add);quick.forEach(add);
    if(result.length<3&&product)add(q(product+' 的型号标签和序列号在哪里查看？','Where can I find the model label and serial number for '+product+'?','确认型号与序列号','Model & serial number'));
    return result.slice(0,3);
  }
  const api={select};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.OntoSuggestions=api;
})(typeof window==='undefined'?this:window);
