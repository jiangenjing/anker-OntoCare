"""Build reviewed bilingual FAQ entries from extracted workbook rows."""
import hashlib,json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
rows=json.loads((BASE/'data/qa-workbooks.json').read_text())
# Topic, workbook, rows, Chinese reviewed answer. Product keys come only from cited PN cells.
specs=[
('error_2310','R',[57], '2310 表示尘盒或滤网未安装到位。\n先取出尘盒并打开盖子，确认滤网是否装好；没有装好时重新安装后再试。\n如果滤网已经正确安装，再对照引用中的图片检查指定位置是否有磁铁。请先确认滤网的安装状态。'),
('error_7031','R',[103], '7031 表示返回基站失败。\n先检查并清理基站周围妨碍回充的障碍物，确认周围空间足够。\n如果仍无法回充，再核对基站是否放在地毯上，并检查万向轮是否缠绕毛发。后续轮胎清洁方式请按引用步骤进行。'),
('power','R',[363,473], '先检查基站是否通电、背部电源线是否插紧，必要时换一个插座。\n将机器人开关拨到 O，等 3–5 秒再拨到 I，等待约 30 秒。随后放回基站并推到底，确认充电触点干净且接触到位。\n若能够开机，待电量超过 30% 再尝试清扫；仍无反应，请反馈基站指示灯状态。'),
('power','B',[54], '先长按电源键 12 秒重置。\n确认吸奶器和充电盒都有电，调整吸奶器在盒内的位置；也可以改用磁吸充电线直接充电。充电后仍无法开机，请联系售后检查。'),
('charge','R',[137], '检查基站电源线两端是否插紧，尤其是连接基站的一端，确认白色环形灯常亮。\n再检查并清洁机器人后部回充模块的充电触点。请告诉我检查后指示灯和电量是否有变化。'),
('charge','R',[136], '确认便携深度清洁器（PDC）已放回基站、基站接通电源，白色环形灯常亮。\n检查并清洁机器人后部回充模块的充电触点，再观察电量是否增加。'),
('charge','R',[503], '确认机器人放在基站上、基站已接通电源，且白色环形灯常亮。\n清洁机器人和基站的充电触点，再观察是否开始充电。'),
('power','R',[503], '先确认机器人放在已通电的基站上，白色环形灯常亮，再清洁机器人和基站的充电触点，观察能否充电并开机。'),
('case_charge','B',[68], '先确认充电盒本身有电。将泵体充电触点对准盒内磁吸接口，放好后应听到咔嗒声、看到白色充电灯闪烁。\n用干布清洁泵体和盒内的磁吸触点，再调整泵体在槽内的位置。'),
('suction','B',[91], '先检查鸭嘴阀和隔膜是否有裂缝、缺口或破损；如有损坏，请停止使用该配件并更换。\n检查鸭嘴阀、法兰通道、隔膜和主机是否装好并密封，佩戴处不要留空隙。\n再检查电量，低电量可能导致吸力下降。请告诉我检查后是吸力偏弱，还是完全没有吸力。'),
('suction','R',[261], '先清洁尘盒滤网、滚刷和滚刷护罩梳齿，再启动一次清扫。\n检查清洁配件是否损坏或老化，必要时更换。若仍吸不干净，请提供未清洁区域的照片或视频，方便进一步判断。'),
('suction','R',[528], '先清洁尘盒滤网、滚刷和梳齿，再启动一次清扫。\n如果仍吸不干净，请提供残留灰尘或毛发区域的照片或视频。'),
('wifi','R',[7], '确认使用的是 2.4GHz Wi-Fi，并核对密码。将机器人、路由器和手机靠近后重试。\n该资料建议将 eufy Clean App 更新到 3.9.2 或以上，再长按电源键重启机器人并重新连接。也可以用手机热点测试网络连接。'),
('wifi','R',[11], 'E25 支持 2.4GHz Wi-Fi，请先核对频段和密码，并把机器人、路由器和手机靠近。\n若仍离线，同时按住电源键和回充键 3 秒，听到网络重置提示后重新配网。还可换一部手机尝试。'),
('wifi','R',[15], 'X10 Pro Omni 支持 2.4GHz Wi-Fi，不支持 5GHz。\n请在路由器中开启 2.4GHz 网络，然后让机器人连接该网络；双频路由器可同时保留原有 5GHz 网络。'),
('wifi','R',[505], '先重启机器人和路由器，核对 Wi-Fi 名称及密码，并确认使用 2.4GHz 网络。\n把基站尽量靠近路由器，避开墙体遮挡和信号盲区。若仍无法连接，请保留配网录屏和路由器型号供售后核查。'),
('app_connect','B',[3], '确认手机蓝牙已打开，且 App 有蓝牙权限。\n重启吸奶器，彻底关闭 App 后重新打开；安卓手机可将 App 加入电池白名单。\n仍无法连接时，在 App 中移除设备后重新添加。'),
('milk_leak','B',[80], '重新检查法兰外圈是否完全密封、鸭嘴阀是否破损。\n佩戴时保持乳头位于法兰通道中央，使用包覆良好的哺乳文胸帮助贴合。结束后先让法兰侧朝上，再取下容器。'),
('dishwasher','B',[93,113], '可水洗配件可以放进洗碗机，但仅限上层。电机主机不可以放入洗碗机。'),
('microwave','B',[94], '不要使用微波炉消毒配件。资料说明，这会使塑料配件变形并造成永久损坏。'),
('recording','B',[225], 'SoloCam S340 不支持 24 小时连续录像，采用事件触发录像以节省电量。'),
('usb_charge','B',[199], '请尝试更换充电线和适配器，使用原装 5V/2A 线材及适配器，并确认充电环境为 0–45°C。\n如果通过 HomeBase 充电，请使用背面的第一个 USB 接口。'),
('solar_charge','B',[130], '检查太阳能板与摄像头的线缆是否插紧、完好，安装位置是否无遮挡且每天有数小时直射阳光；充电温度应在 0–45°C。\n在 App 的电源管理中检查电源模式设置。若插座充电正常而太阳能不充电，可用另一块兼容太阳能板交叉测试。'),
('offline','B',[187], '先检查电量，电量过低时先充电。按一下 SYNC 键，若指示灯不亮，可长按 2 秒开机。\n将摄像头移近路由器，并确认有独立的 2.4GHz 网络。仍离线时，在 App 中移除摄像头后重新添加。'),
('dock_7033','R',[78], '先检查基站是否通电、白色环形灯是否亮起。\n把机器人放到基站外，按回充键，观察能否回站并充电。清扫期间不要关闭或移动基站，并保持回站路径上的门打开。'),
]
entries=[]
for topic,book,nums,zh in specs:
 filename='eufy '+('Robovacs' if book=='R' else 'Breast Pump')+' Q&A.xlsx'
 refs=[next(r for r in rows if r['source_file']==filename and r['source_row']==n) for n in nums]
 pns=set(refs[0]['PN'].split(';'))
 for r in refs[1:]:pns&=set(r['PN'].split(';'))
 for pn in sorted(pns):
  entries.append(dict(pn=pn,topic=topic,answer_zh=zh,answer_en='\n\n'.join(r['Content'].strip() for r in refs),
   sources=[{'file':r['source_file'],'sheet':r['source_sheet'],'row':r['source_row'],'sha256':r['source_sha256'],'content_sha256':hashlib.sha256((r['Title']+'\n'+r['Content']).encode()).hexdigest()} for r in refs]))
payload=dict(version='faq-reviewed-1',entries=entries)
(BASE/'data/faq-cache.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
print('Workflow definitions',len(specs),'Product-topic keys',len(entries))
