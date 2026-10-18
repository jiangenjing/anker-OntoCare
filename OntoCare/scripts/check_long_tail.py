"""Run ten reproducible checks against the configured model; never prints credentials."""
import json,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import app
CASES=[
('只收到配件包，主机没到，怎么办？','L001','理解您收到配件却没收到主机的着急。\n\n需要按商品和包裹分别核对，配件签收不能说明主机已送达；目前没有您的订单资料，不能确认物流状态。\n\n请提供订单号，我帮您核对主机对应的包裹。'),
('物流单号显示 label created 后无更新','L002','理解您想知道包裹是否真正寄出了。\n\n标签创建与实际揽收需要分开核对，目前没有当前包裹的扫描记录，无法确认送达时间。\n\n请提供订单号或物流单号。'),
('物流显示 in transit，预计到达时间已过','L003','超过预计日期还没收到，确实会让人担心。\n\n需要核对该包裹最新扫描和原预计日期；预计日期不等于保证送达时间，目前也没有发起承运商查询。\n\n请提供订单号，以便确认需要核查的包裹。'),
('物流显示 Return to sender，但我没收到退款','L004','理解您既没收到包裹，也没收到退款的困扰。\n\n退回寄件人的物流状态不能证明退款已办理，需要分别核对物流及退款记录，资格由购买渠道审核。\n\n您希望申请重新寄送，还是核查退款？'),
('客户要求指定承运商，可以选吗？','L009','理解您希望选择更合适的承运商。\n\n是否支持指定，需要核对购买渠道的配送规则；目前没有已确认的规则，不能保证仓库采纳，也尚未提交备注。\n\n请告诉我购买渠道。'),
('T8170 夜视效果差','C004','了解，您遇到的是 T8170 夜视画面问题。\n\n补充策略建议核对镜头是否脏污、附近墙面或灯源是否造成反光，并检查安装角度；具体操作仍需对照该型号说明。\n\n画面主要是过曝发白，还是整体太暗？'),
('T8170 图像模糊','C005','了解，您想改善 T8170 的画面清晰度。\n\n补充策略建议先检查镜头表面污渍、凝露及附近反光物；目前不能据此判断硬件损坏。\n\n镜头表面能看到水汽或污渍吗？'),
('T8170 误报太多','C007','频繁收到误报确实会影响使用。\n\n补充策略建议检查检测灵敏度、活动区域及热源或树木干扰，再对照该型号功能设置调整；目前没有替您更改任何配置。\n\n误报通常由车辆、树木还是其他目标触发？'),
('T2351 7053 设备倾斜','R063','了解，设备出现了倾斜提示。\n\n先按 T2351 对应资料核对 7053，检查机器是否位于平整地面；具体建议以原始 Q&A 为准，不能直接判定故障或承诺换新。\n\n机器移到平整地面后，是否仍提示同一错误？'),
('T8D04 充电盒或配件熔化','B010','出现熔化需要优先处理安全问题。\n\n请停止使用和充电，保留故障照片供人工核查；不能仅凭描述认定是消毒方式导致，也不能直接承诺换新。\n\n熔化的是充电盒还是可拆卸配件？')]

def run(pair):
 i,(q,ident,predicted)=pair;start=time.time()
 with app.app.test_client() as c:
  d=c.post('/api/chat',json={'message':q,'session_id':f'json-check-{i}'}).get_json()
  citations=d.get('citations',[])
  checks={'has_reply':bool(d.get('reply')),'has_citations':bool(citations),'citations_open':all(c.get(x['url']).status_code==200 for x in citations),'no_foreign_order':not any(x in d.get('reply','') for x in ['Anker1234567','ANKER001','Anker001']),'model_ok':d.get('trace',{}).get('model_status')=='OK'}
  return {'number':i,'question':q,'candidate':'long-tail-json-'+ident,'predicted_reply':predicted,'actual_reply':d.get('reply'),'citations':citations,'trace':d.get('trace'),'seconds':round(time.time()-start,2),'checks':checks}
if __name__=='__main__':
 results=list(ThreadPoolExecutor(max_workers=3).map(run,enumerate(CASES,1)))
 folder=ROOT/'reports';folder.mkdir(exist_ok=True)
 (folder/'长尾10题实测.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 text='# 长尾场景：10 道抽查题与预期回复\n\n预期回复是验收参考，不要求模型逐字复述。实际回复及引用来自本次真实模型调用。产品原始 Q&A、安全规则优先，因此候选补充条目不一定成为最终引用。引用链接需要启动本地服务。\n\n'
 for r in results:
  text+=f"## {r['number']}. {r['question']}\n\n候选策略：{r['candidate']}\n\n### 预期回复\n\n{r['predicted_reply']}\n\n### 本次实际回复\n\n{r['actual_reply']}\n\n"
  text+='引用：'+'；'.join(f"[{x['id']}](http://127.0.0.1:5088{x['url']})" for x in r['citations'])+'\n\n'
  text+=f"校验：{json.dumps(r['checks'],ensure_ascii=False)}；模型状态：{r['trace']['model_status']}；用时 {r['seconds']} 秒。\n\n"
 (ROOT/'docs/reports/长尾场景：10 道抽查题与预期回复.md').write_text(text)
 print(json.dumps([{'n':r['number'],'checks':r['checks'],'route':r['trace']['answer_route'],'refs':[c['id'] for c in r['citations']]} for r in results],ensure_ascii=False,indent=2))
