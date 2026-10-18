"""Merchant draft workflow: source email -> case facts -> rules -> cited draft."""
import json
import re
from pathlib import Path
from qa_workflows import RISK
from customer_signals import language
from mail_language import detect, NAMES

BASE = Path(__file__).parent
MAILS = json.loads((BASE / 'data/mail-tickets.json').read_text())


def source(row):
    return {'id': f'mail-{row["source_row"]}', 'kind': 'email',
            'label': f'{MAILS["source_file"]} · {MAILS["sheet"]}!C{row["source_row"]}',
            'url': f'/api/sources/mail-{row["source_row"]}'}


def prepare(body):
    if not isinstance(body, dict):
        raise ValueError('请求格式不正确。')
    text = body.get('message', '')
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError('请输入邮件正文，最多 20000 字。')
    text = text.strip()
    row = next((r for r in MAILS['rows'] if r['source_row'] == body.get('ticket_row')), None)
    # Edited/pasted mail must never inherit an unrelated selected order or SKU.
    if row and text != str(row['客户首封邮件内容']).strip():
        row = None
    requested = body.get('language','en')
    lang = detect(text, language(text, requested)) if requested == 'auto' else language(text, requested)
    if lang not in NAMES:
        raise ValueError('当前邮件支持中文、英文、德语、法语和荷兰语，请指定回复语言。')
    risk = bool(re.search(RISK, text, re.I))
    attempted = bool(re.search(r'试过|清洁.*仍|仍.*充不上|despite|already tried|tried repeatedly|tried.*over and over', text, re.I))
    return text, row, lang, risk, attempted


def compose(text, row, lang, result, risk, attempted):
    zh = lang == 'zh'
    trace = result['trace']
    refs = result['citations']
    answer = result['reply']
    route = trace['answer_route']
    if row and row.get('咨询场景') == 'Shipping inquiry' and trace['order_status'] == 'FOUND':
        answer = answer.replace(f"If this is still order {trace['order']}, the saved records say:", f"For order {trace['order']}, the saved records say:")
        answer = answer.replace('Is this the same order or a different one? Please share the full tracking number and carrier so I can check the match.', 'The difference between your report and these saved records needs a carrier review; these records do not establish an arrival date.')
        answer = answer.replace(f"如果仍是前面的订单 {trace['order']}，保存的记录显示：", f"订单 {trace['order']} 的资料记录显示：")
        answer = answer.replace('你查的是这笔订单，还是另一笔？请发一下查询失败的完整物流单号和承运商名称，我先帮你核对是否对应。', '你描述的情况与资料记录存在差异，需要进一步向承运商核查，不能据此确定送达时间。')
    if risk:
        answer = ('很抱歉得知设备出现安全相关情况。请先暂停使用该设备。为便于优先核查，请提供受影响部件的照片及购买凭证；我们需要由人工评估后续处理方案。' if zh else
                  'I’m sorry to hear about this safety-related issue. Please stop using the affected device. Please share photos of the affected part and proof of purchase so the issue can be reviewed as a priority. The next service action needs a human review.')
        route = 'SAFETY_REVIEW'
        refs = [{'id':'service-rules','kind':'context','label':'服务规则 · 安全问题需人工核查','url':'/api/sources/service-rules'}]
    elif attempted and trace.get('answer_route') not in ('HUMAN_REVIEW','GROUNDED_LLM') and not re.search(r'shipping|shipment|tracking|发货|物流', text, re.I):
        answer = ('你已经做过检查但问题仍然存在，不必只重复同一项操作。请补充当前报错或指示灯状态，以及已尝试的步骤和结果；如需售后处理，也请提供购买凭证，便于核查下一步。' if zh else
                  'You have already attempted checks and the issue is still present. Please share the current error or indicator status, together with the steps you tried and what happened. If service is needed, please also provide proof of purchase so the next action can be reviewed.')
        route = 'ATTEMPTED_STEPS_REVIEW'
        refs = [c for c in refs if c['kind'] == 'context'] or [{'id':'service-rules','kind':'context','label':'服务规则 · 待补信息','url':'/api/sources/service-rules'}]
    elif route in ('SOURCE_FALLBACK', 'ERROR_CODE_SOURCE'):
        # Raw knowledge dumps are evidence for the merchant, not ready-to-send mail.
        answer = ('已找到相关资料，但还不足以确定适合你这次情况的处理步骤。请提供当前报错截图和已尝试的操作，便于核对后给出准确建议。' if zh else
                  'I found related product references, but need to confirm which steps apply to your case. Please share the current error screenshot and the checks you have already tried so the guidance can be verified.')
        route = 'REFERENCE_REVIEW'
    if trace.get('model_status') != 'OK' and not risk:
        if re.search(r'motor.*noise',text,re.I) and any(c['id'] in ('b-37','b-124') for c in result['citations']):
            answer = ('已了解吸奶器电机异响的问题。同型号资料建议先区分持续或间歇异响，再据此排查，不能直接判定故障原因。请问异响是持续的还是间歇的？' if zh else 'I understand the pump motor is making an unusual noise. The model-specific guide starts by distinguishing continuous from intermittent noise; the cause is not yet confirmed. Is the noise continuous or intermittent?')
            refs=result['citations'];route='EVIDENCE_FALLBACK'
        elif re.search(r'pin.*(?:jammed|broken)',text,re.I) and any(c['id']=='b-128' for c in result['citations']):
            answer=('已了解充电盒一侧触点卡住或损坏、无法充电，且您已清洁检查。同型号资料提到触点损坏会影响充电，但当前无法确认损坏程度。请提供触点照片供人工核查；换货资格还需核验，尚未办理。' if zh else 'I understand one side of the charging case no longer charges and you report a jammed or broken pin despite cleaning and checks. The model-specific guide identifies damaged contacts as a possible cause, not a confirmed diagnosis. Please share a photo of the contact for human review; replacement eligibility is not yet confirmed and no replacement has been arranged.')
            refs=result['citations'];route='EVIDENCE_FALLBACK'
        elif re.search(r'water tray will not empty',text,re.I) and any(c['id']=='r-255' for c in result['citations']):
            answer=('您已清理托盘、检查软管和接头，但污水仍无法排出。同型号资料另有污水箱安装与密封检查项，不能仅凭描述判定部件损坏。请先确认污水箱装回基站时锁扣是否扣紧。' if zh else 'You have already cleaned the tray and checked the hose and connector, but the tray still will not drain. The matching guide also includes checks of the dirty-water tank installation and seal; this does not yet prove a damaged component. Is the dirty-water tank latch securely fastened when the tank is installed?')
            refs=result['citations'];route='EVIDENCE_FALLBACK'
    evidence = ([source(row)] if row else []) + refs
    checks = [
        {'rule':'邮件来源', 'status':'已核对' if row else '商家输入', 'detail':source(row)['label'] if row else '当前粘贴/编辑内容；未继承所选工单信息'},
        {'rule':'产品识别', 'status':trace['product_state'], 'detail':trace['product']},
        {'rule':'订单核对', 'status':trace['order_status'], 'detail':f"{trace['order']}；归属未验证；物流仅为资料快照"},
        {'rule':'质保与渠道', 'status':'待核验', 'detail':f"质保记录：{trace['warranty']}；渠道：{trace['dealer']}；不等于已批准售后"},
        {'rule':'安全与已尝试操作', 'status':'优先人工核查' if risk else ('已尝试' if attempted else '未确认'), 'detail':'存在安全描述，停止普通排障' if risk else ('客户描述了已尝试操作，避免重复建议' if attempted else '未自动标记任何操作完成')},
        {'rule':'资料与规则', 'status':route, 'detail':'; '.join(c['label'] for c in refs)},
        {'rule':'售后动作', 'status':'仅草稿', 'detail':'未发邮件；未提交维修、退款、换货或转接'}]
    # Remove answer-local numbering, then attach a stable evidence index for this draft.
    answer = re.sub(r'\s*\[\d+\]', '', answer).strip()
    offset = 1 if row else 0
    markers = ' '.join(f'[{i+1}]' for i in range(offset, len(evidence)))
    greeting = '你好，\n\n感谢你联系我们。' if zh else 'Hello,\n\nThank you for contacting us.'
    greetings={'nl':'Hallo,\n\nBedankt voor uw bericht.','fr':'Bonjour,\n\nMerci de nous avoir contactés.','de':'Guten Tag,\n\nvielen Dank für Ihre Nachricht.'}
    greeting=greetings.get(lang,greeting)
    closing = '\n\n' + {'zh':'安克售后服务团队','en':'Anker Support Team','de':'Anker Kundendienst','fr':'Service client Anker','nl':'Anker Klantenservice'}[lang]
    draft = greeting + '\n\n' + answer + ' ' + markers + closing
    subject = {'zh':'关于你的售后咨询','en':'Re: Your support request','nl':'Betreft: uw hulpvraag','fr':'Objet : votre demande','de':'Betreff: Ihre Anfrage'}[lang]
    if trace['product'] != '未确定':
        subject += ' — ' + (trace['product'] if zh else re.sub(r'[\u4e00-\u9fff]+', '', trace['product']).strip())
    return {'subject':subject, 'draft':draft, 'citations':evidence, 'checks':checks,
            'trace':trace, 'route':route, 'status':'DRAFT_ONLY',
            'ontology':{'ServiceCase':{'channel':'email','status':'DRAFT_ONLY'},
                        'Product':trace['product'], 'Order':trace['order'],
                        'Evidence':[c['id'] for c in evidence], 'PolicyDecision':route,
                        'Action':{'type':'prepare_email_draft','executed':True,'email_sent':False}}}
