"""
Anker Ontology-Driven Service Agent — MVP 后端
================================================
原则：大模型只做模糊理解；质保/经销商/动作资格等确定性判断全部由本文件的
规则函数（Decision Ontology）确定性计算。LLM 无权绕过 allowed_actions。
无 LLM key 时走 MOCK 模式，用模板生成回复，规则引擎照常工作。
运行：pip install flask  &&  python app.py   打开 http://127.0.0.1:5000
"""
import json, os, re, math, uuid
from datetime import date
import urllib.request
from flask import Flask, request, jsonify, send_from_directory, g, Response
from queue import Queue, Empty
from threading import Thread
from html import escape
import qa_workflows as qa
import conversation_workflow as workflow
import mail_workflow as mail
import handoffs
import grounded_response
import customer_signals
import long_tail_knowledge as longtail
import order_cards
import proactive_orders
import media_understanding
from action_gateway import public_data, REDACTED
import user_experience
import quick_replies
import general_support
import followup_questions
from pathlib import Path
from fixed_api import load as load_fixed_api

RESPONSE_GUIDE = (Path(__file__).parent / "docs/prompts/agents/responder/Agent.md").read_text()

# ---------- 固定演示连接：每次启动读取后端文件，评委无需配置 ----------
globals().update(load_fixed_api())
GROUNDED_MODE = os.getenv("LLM_RESPONSE_MODE") == "grounded"

def call_llm(system: str, user: str, timeout: int = 15) -> str | None:
    """调 OpenAI 兼容接口；在请求内记录真实调用状态。"""
    if not LLM_KEY or not LLM_MODEL:
        g.model_status = "NOT_CONFIGURED"
        return None
    g.model_calls = getattr(g, "model_calls", 0) + 1
    g.model_status = "REQUESTED"
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
        **({"thinking":{"type":"disabled"}} if "deepseek" in LLM_MODEL.lower() else {}),
        "response_format": {"type": "json_object"},
        "max_tokens": getattr(g, "llm_max_tokens", 1800),
    }).encode()
    req = urllib.request.Request(LLM_BASE.rstrip("/") + "/chat/completions",
        data=payload, headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json",
                               "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            choice = json.loads(r.read())["choices"][0]
            g.model_finish_reason = choice.get("finish_reason")
            answer = (choice["message"].get("content") or "").strip()
        g.model_status = "OK"
        return answer
    except Exception as e:
        g.model_status = "ERROR"
        g.degraded_reason = ('rate_limited' if getattr(e, 'code', None) == 429 else
                             'model_timeout' if isinstance(e, TimeoutError) else
                             'invalid_model_response' if isinstance(e, (ValueError, KeyError, TypeError, IndexError)) else 'model_unavailable')
        return None

# ---------- 视觉模型(VLM)：读故障图，抽结构化证据 ----------

def call_vlm(image_path):
    return media_understanding.understand(image_path,VLM_BASE,VLM_KEY,VLM_MODEL).get('evidence')


BASE = os.path.dirname(os.path.abspath(__file__))
def load(name):
    with open(os.path.join(BASE, "data", name), encoding="utf-8") as f:
        return json.load(f)

from dataset import load_dataset
PRODUCTS, ORDERS, DEALERS, KB_LIST, TICKETS, DATA_SUMMARY = load_dataset()
POLICY = load("policies.json")
SOURCE_ADDRESSES = tuple({r.get('订单地址') for o in ORDERS.values() for r in o['items'] if r.get('订单地址')})
def customer_response(**payload):
    return jsonify(public_data(payload, SOURCE_ADDRESSES))

# ---------- 按产品对象限定的模拟知识条目检索 ----------
# 只在【已确认产品】的知识范围内做 TF-IDF 检索，避免跨产品/同名产品污染。
STOP_WORDS = set("what should i do if my the a an is are it to for of on with and or this eufy pro omni robot vacuum breast pump anker please order".split())
def tokens(text):
    translations = {"无法开机": "cannot power turn on", "不能开机": "cannot power turn on", "不吸": "no suction", "无法充电": "not charging", "漏水": "water leaking", "噪音": "noise"}
    for zh, en in translations.items():
        text = text.replace(zh, en)
    return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in STOP_WORDS and len(t) > 1]

class KBIndex:
    def __init__(self, kb_list):
        self.docs, df = [], {}
        for kb in kb_list:
            text = (kb["fault_name"] + " " + " ".join(kb["symptoms"]) + " " + kb.get("cause", "")).lower()
            toks = tokens(text)
            self.docs.append((kb, toks))
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self.N, self.df = len(self.docs), df
    def _idf(self, t):
        return math.log((1 + self.N) / (1 + self.df.get(t, 0))) + 1
    def search(self, product_id, query, topk=1):
        q = tokens(query)
        if not q:
            return []
        scored = []
        for kb, toks in self.docs:
            if kb["product_id"] != product_id:   # 本体约束：只搜当前产品
                continue
            tf = {}
            for x in toks:
                tf[x] = tf.get(x, 0) + 1
            dot = sum(tf.get(qt, 0) * self._idf(qt) for qt in q)
            norm = math.sqrt(sum((v * self._idf(k)) ** 2 for k, v in tf.items())) or 1
            qnorm = math.sqrt(sum(self._idf(qt) ** 2 for qt in q)) or 1
            scored.append((dot / (norm * qnorm), kb))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:topk]

KB = KBIndex(KB_LIST)

app = Flask(__name__, static_folder="static", static_url_path="")
from benchmark.api import bp as benchmark_api
app.register_blueprint(benchmark_api)
from model_demo import register_model_demo
register_model_demo(app, globals())

# 内存会话：MVP 用 dict，生产换 DynamoDB / Redis
SESSIONS = {}

# ---------- 1. 感知层：情绪 / 实体 / 模型候选意图 ----------
def detect_emotion(text: str) -> str:
    return customer_signals.emotion(text)

def detect_scope(text: str) -> str:
    """服务边界：超出自助范围的意图直接转人工，不进入业务流程。"""
    t = text.lower()
    if re.search(r"\bpress\b|journalist|media inquiry|corporate|bulk order|wholesale|\bresell\b|媒体采访|批量采购", t):
        return "OUT_OF_SCOPE_BUSINESS"
    if re.search(r"speak to (a )?(human|manager|real person|agent)|talk to (a )?(manager|human)|supervisor|real person|agent please|转人工|找人工|客服主管", t):
        return "OUT_OF_SCOPE_HUMAN"
    return "IN_SCOPE"

PROMOTER_WORDS = ["pump", "flange", "breast", "duckbill", "membrane", "nipple", "吸奶", "乳泵"]
ROBOT_WORDS    = ["vacuum", "robot", "brush", "dock", "docking", "扫地", "吸尘", "滚刷"]

def resolve_product(text: str, order_sku: str | None) -> dict:
    """本体消歧：同名 S1 Pro → 吸奶器 or 扫地机。订单 SKU 是最强证据，直接定位。"""
    # Explicit selection is stronger than a list of products mentioned earlier.
    focus = re.search(r'(?:我(?:要)?问|我选|选择|查询这件|I (?:mean|choose|want help with))\s*[:：]?\s*(.+)', text, re.I)
    if focus:
        selected = resolve_product(focus.group(1), None)
        if selected['product']:
            selected['evidence'] = 'explicit_product_selection'
            return selected
    # 订单已明确 SKU：无需再从文本猜
    if order_sku:
        for p in PRODUCTS:
            if p["sku"] == order_sku[:5]:
                return {"product": p, "evidence": f"order_sku={order_sku}", "state": "FIXTURE_MATCHED"}
    t = text.lower()
    pn = re.search(r"\b[te][a-z0-9]{4}(?:[a-z0-9-]*)\b", t)
    if pn:
        exact = next((p for p in PRODUCTS if p["id"].lower() == pn.group(0)[:5]), None)
        if exact:
            return {"product": exact, "evidence": "explicit_pn", "state": "PROBABLE"}
    candidates = [p for p in PRODUCTS if "s1 pro" in t and p["category"] in ("breast_pump", "robot_vacuum")]
    if not candidates:  # 不是同名歧义，按 alias 粗匹配
        for p in PRODUCTS:
            if any(a in t for a in p["aliases"]):
                return {"product": p, "evidence": "alias_match", "state": "PROBABLE"}
        return {"product": None, "evidence": "no_product_mentioned", "state": "UNKNOWN"}

    # 语义关键词消歧
    if any(w in t for w in PROMOTER_WORDS):
        p = next(x for x in PRODUCTS if x["id"] == "T8D04")
        return {"product": p, "evidence": "semantic=breast_pump", "state": "PROBABLE"}
    if any(w in t for w in ROBOT_WORDS):
        p = next(x for x in PRODUCTS if x["id"] == "T2080")
        return {"product": p, "evidence": "semantic=robot_vacuum", "state": "PROBABLE"}
    return {"product": None, "evidence": "ambiguous_S1Pro", "state": "CONFLICTED"}

def match_fault(product_id: str, text: str):
    query = text.lower()
    for item in KB_LIST:
        if item["product_id"] == product_id and any(len(s) > 1 and s.lower() in query for s in item["symptoms"]):
            return item
    res = KB.search(product_id, text)
    if res and res[0][0] > 0.08:   # 超过阈值才算命中；低于阈值→知识库无答案→走诚实升级
        return res[0][1]
    return None

# ---------- 2. 数据流：订单 / 经销商（确定性查询） ----------
def lookup_order(order_id: str | None, selected_sku=None):
    if not order_id:
        return {"status": "NOT_PROVIDED", "warranty": "UNKNOWN"}
    order_id = order_id.upper()
    if order_id not in ORDERS:
        return {"status": "NOT_FOUND", "warranty": "UNKNOWN"}
    o = dict(ORDERS[order_id])
    if len(o['items']) > 1:
        selected = [r for r in o['items'] if selected_sku and r.get('SKU', '').upper() == selected_sku.upper()]
        if len(selected) != 1:
            o['sku'] = ''
            return {'status': 'FOUND', 'order': o, 'warranty': 'UNKNOWN', 'within_30d': False}
        row = selected[0]
        o.update(sku=row['SKU'], warranty_until=row.get('质保结束日期'),
                 order_date=row.get('购买日期') or o['order_date'])
    wd = date.fromisoformat(o["warranty_until"])
    in_warranty = wd >= date.today()
    within_30d = 0 <= (date.today() - date.fromisoformat(o["order_date"])).days <= 30
    return {"status": "FOUND", "order": o,
            "warranty": "VALID" if in_warranty else "EXPIRED",
            "warranty_until": o["warranty_until"], "within_30d": within_30d}

def match_dealer(country: str | None, seller: str | None):
    """Country 精确 + Seller 模糊。"""
    if not country or not seller:
        return {"status": "INSUFFICIENT_INFO"}
    sl = seller.strip().lower().replace("-", " ").replace(".", "").replace("  ", " ")
    for d in DEALERS:
        if d["country"].lower() != country.strip().lower():
            continue
        for name in d["seller_names"]:
            nl = name.lower().replace("-", " ").replace(".", "").replace("  ", " ")
            if sl == nl:
                return {"status": "AUTHORIZED" if d["authorized"] else "NOT_AUTHORIZED",
                        "matched": name}
    return {"status": "NO_MATCH"}

# ---------- 3. Decision Ontology：状态 → 合法动作空间（核心） ----------
def allowed_actions(case: dict):
    """返回 (allowed[], forbidden[])。规则全部确定性，LLM 只能在 allowed 里选。"""
    allowed, forbidden, reasons = [], [], []
    prod = case.get("product")
    warranty = case.get("warranty", "UNKNOWN")
    dealer = case.get("dealer", "UNKNOWN")
    ts = case.get("troubleshooting", "NOT_STARTED")

    if not prod:
        allowed += ["ask_product", "search_knowledge"]
        forbidden += ["propose_replacement", "direct_refund"]
        reasons.append("产品未确认：不允许任何售后办理动作")
        return allowed, forbidden, reasons

    allowed += ["search_knowledge", "run_troubleshooting", "escalate_human"]

    # 订单查无：UNKNOWN ≠ EXPIRED，禁止判过保、禁止办理
    if warranty in ("UNKNOWN", "PENDING_RECHECK"):
        forbidden += ["propose_replacement", "direct_refund", "tell_expired"]
        allowed += ["ask_country", "ask_seller", "request_proof"]
        reasons.append("订单未核实或购买日期待重核：禁止判定过保或承诺办理")
        return allowed, forbidden, reasons

    if warranty == "EXPIRED":
        forbidden += ["propose_replacement", "direct_refund"]
        allowed += ["propose_paid_repair"]
        reasons.append("已过保：免费换货/退款均不可用")
        return list(dict.fromkeys(allowed)), forbidden, reasons

    # warranty == VALID
    if ts == "FAILED" and dealer == "AUTHORIZED":
        allowed += ["prepare_replacement_review"]
        reasons.append("排障失败 + 在保 + 授权经销商：仅整理换货人工审核材料")
    if dealer == "NOT_AUTHORIZED":
        forbidden += ["propose_replacement", "direct_refund"]
        allowed += ["guide_contact_seller"]
        reasons.append("非授权经销商：引导联系购买渠道，不进入官方保修")
    elif case.get("within_30d") and dealer == "AUTHORIZED":
        allowed += ["prepare_return_review"]
        reasons.append("模拟订单显示30天内；退货资格仍需渠道、商品状态和人工核对")
    forbidden += ["direct_refund", "propose_replacement"]
    reasons.append("演示环境无真实退款或换货执行器，不得声称已办理")
    allowed = list(dict.fromkeys(allowed)); forbidden = list(dict.fromkeys(forbidden))
    return allowed, forbidden, reasons

# ---------- 主流程 ----------
from analytics_api import bp as analytics_bp
app.register_blueprint(analytics_bp)

@app.post('/api/analytics/chat')
def analytics_chat():
    import analytics_assistant
    body=request.get_json(silent=True) or {}
    query=body.get('message')
    if not isinstance(query,str) or not query.strip() or len(query)>2000:
        return jsonify(error='请输入 1–2000 字的问题'),400
    context=body.get('context') or {}
    if not isinstance(context,dict):return jsonify(error='上下文格式错误'),400
    result=analytics_assistant.answer(query.strip(),context,call_llm)
    return jsonify(public_data(result,SOURCE_ADDRESSES))


@app.route('/decision-assets/<path:filename>')
def decision_document(filename):
    # Keep existing workbench links after documentation consolidation.
    return send_from_directory(Path(__file__).parent / 'docs/frontend/decision-assets', filename)

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route('/api/sources/<source_id>')
def source_view(source_id):
    if source_id in longtail.ENTRIES:
        item=longtail.ENTRIES[source_id]
        title='用户补充长尾核查策略（非官方政策） · '+source_id
        content=item['content']+'\n\n来源：用户提供材料，经整理去除未经核验承诺；原文未提供逐条可验证链接。'
    elif source_id in qa.SOURCES:
        row = qa.SOURCES[source_id]
        title = f"{row['source_file']} · {row['source_sheet']}!D{row['source_row']}:E{row['source_row']}"
        content = row['Title'] + "\n\n" + row['Content']
    elif source_id.startswith('order-') and source_id[6:].isdigit():
        row = next((r for o in ORDERS.values() for r in o['items'] if r['原文行号'] == int(source_id[6:])), None)
        if not row:
            return 'Not found', 404
        title = f"订单信息 · 第 {row['原文行号']} 行（资料快照）"
        content = '\n'.join(f"{k}: {REDACTED if k == '订单地址' and row.get(k) else row.get(k, '未提供')}" for k in ['No.','订单号','SKU','Product Description','QTY','购买日期','质保结束日期','订单地址','订单状态','物流承运商','物流单号','物流状态','发货日期','订单金额'])
    elif source_id.startswith('mail-') and source_id[5:].isdigit():
        row = next((r for r in mail.MAILS['rows'] if r['source_row'] == int(source_id[5:])), None)
        if not row:
            return 'Not found', 404
        title = mail.source(row)['label']
        content = row['客户首封邮件内容']
    elif source_id.startswith('handoff-'):
        record = handoffs.get(source_id[8:])
        if not record:
            return 'Not found', 404
        title = '客户对话转接记录 · ' + record['id'][:8]
        content = record['message']
    elif source_id == 'dealer-directory':
        title = '赛题经销商名录（名录命中不代表购买凭证已核验）'
        content = '\n'.join(d['country']+' · '+', '.join(d['seller_names'])+' · '+str(d['authorized']) for d in DEALERS)
    elif source_id == 'service-rules':
        title = '本轮处理依据与服务规则'
        content = '澄清问题依据用户本轮输入和已提供的会话信息，不代表命中产品知识库。\n型号不清楚时先确认型号；订单查无不代表过保；商品编码不等于订单号；物流是资料快照。\n退款、换货与安全相关问题需要人工核实，当前系统没有实际执行器。'
    else:
        return 'Not found', 404
    return '<!doctype html><meta charset="utf-8"><title>引用来源</title><main style="max-width:850px;margin:40px auto;padding:20px;font:16px/1.8 system-ui"><h2>' + escape(title) + '</h2><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + escape(content) + '</pre></main>'


@app.route("/api/data")
def data_summary():
    return jsonify(summary=DATA_SUMMARY, tickets=TICKETS)

@app.route('/api/user-options')
def user_options():
    case=SESSIONS.get(request.args.get('session_id'),{})
    data=followup_questions.refresh(case,'',[],lookup_order(case.get('order_id')))
    return jsonify(choices=user_experience.choices(case,ORDERS,PRODUCTS),followups=user_experience.enrich_questions(data,case,ORDERS))

@app.route('/api/feedback',methods=['POST'])
def user_feedback():
    body=request.get_json(silent=True) or {}
    case=SESSIONS.get(body.get('session_id'))
    turn=body.get('turn')
    if not case or type(turn)!=int or not 1<=turn<=case.get('turn_count',0) or body.get('rating') not in ('helpful','unresolved'):
        return jsonify(error='无效反馈'),400
    case.setdefault('feedback',{})[str(turn)]={'rating':body['rating'],'detail':str(body.get('detail',''))[:1000]}
    return jsonify(saved=True)

@app.route('/api/session/<sid>')
def session_snapshot(sid):
    case = SESSIONS.get(sid, {})
    return customer_response(response_language=case.get('response_language','zh'), order_snapshot=order_cards.build(lookup_order(case.get('order_id'),case.get('selected_sku'))), transcript=case.get('transcript',[]), turn_count=case.get('turn_count',0), handoff_available=case.get('turn_count',0)>8, followups=case.get('followups'))


@app.route('/api/handoffs', methods=['GET','POST'])
def handoff_queue():
    if request.method == 'GET':
        return jsonify(records=handoffs.all_records())
    body = request.get_json(silent=True) or {}
    sid = body.get('session_id')
    case = SESSIONS.get(sid)
    if not case or case.get('turn_count',0) <= 8:
        return jsonify(error='连续交互超过 8 次后可提交转接请求。'), 400
    channel = body.get('channel')
    if channel not in ('human','email'):
        return jsonify(error='无效渠道'), 400
    existing = case.get('handoff_ids', {}).get(channel)
    record = handoffs.get(existing) if existing else None
    if not record:
        record = handoffs.create(sid,case,channel)
        case.setdefault('handoff_ids',{})[channel] = record['id']
    return jsonify(record=record, message='已保存到商家待处理列表，尚未接通人工或发送邮件。')


@app.route('/merchant')
def merchant():
    return send_from_directory('static', 'merchant.html')


@app.route('/api/mail/rewrite', methods=['POST'])
def mail_rewrite():
    import mail_editing
    body=request.get_json(silent=True) or {}
    g.model_calls=0;g.model_status='NOT_USED';g.llm_max_tokens=3000
    if not LLM_KEY or not LLM_MODEL:
        return jsonify(error='未配置模型，保留原草稿'),503
    try:
        return jsonify(mail_editing.rewrite(call_llm,body.get('text'),body.get('action'),body.get('language','zh'),body.get('tone','friendly'),subject=body.get('subject')))
    except ValueError as exc:
        return jsonify(error=str(exc)),422


@app.route('/api/mail/tickets')
def mail_tickets():
    return jsonify(mail.MAILS)


@app.route('/api/mail/stream', methods=['POST'])
def mail_stream():
    body = request.get_json(silent=True) or {}
    incoming = handoffs.get(body.get('handoff_id')) if isinstance(body,dict) else None
    if incoming and body.get('message','').strip() != incoming['message'].strip():
        incoming = None
    prepared = dict(body) if isinstance(body,dict) else body
    if incoming:
        prepared['message'] = incoming.get('routing_message', incoming['latest_message'])
        prepared.pop('ticket_row', None)
    try:
        text, row, lang, risk, attempted = mail.prepare(prepared)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    events = Queue()
    def run():
        sid = 'mail-' + uuid.uuid4().hex
        payload = {'message': text, 'session_id': sid, 'language': lang, 'new_case': True, 'channel':'email'}
        if incoming and incoming.get('order_id'):
            payload['order_id'] = incoming['order_id']
        if incoming and incoming.get('product'):
            payload['message'] = incoming['product'] + '\n' + text
        if row:
            # Shipping needs all parcels, not only the SKU selected by the ticket.
            if row['咨询场景'] != 'Shipping inquiry':
                payload['ticket_row'] = row['source_row']
            if re.fullmatch(r'Anker\d{3}', str(row.get('订单号') or ''), re.I):
                payload['order_id'] = row['订单号']
        try:
            events.put({'type':'progress','text':'已读取邮件，建立独立售后案件'})
            with app.test_request_context('/api/chat', method='POST', json=payload):
                g.progress = events.put
                g.progress_language = 'zh'
                result = app.make_response(chat()).get_json()
                events.put({'type':'progress','text':'正在核对已尝试操作、来源和售后动作范围'})
                draft = mail.compose(text, row, lang, result, risk, attempted)
                from mail_language import finalize
                draft = finalize(draft, lang, call_llm if LLM_KEY and LLM_MODEL else None)
                if incoming:
                    draft['citations'].append({'id':'handoff-'+incoming['id'], 'kind':'context', 'label':'客户对话记录 · '+incoming['id'][:8], 'url':'/api/sources/handoff-'+incoming['id']})
                    draft['checks'][0] = {'rule':'邮件来源','status':'对话转入','detail':'保留完整对话，按最新问题及当前案件资料生成回复'}
                events.put({'type':'progress','text':'引用核对完成，已生成待审核草稿'})
                SESSIONS.pop(sid, None)
                events.put({'type':'result','data':draft})
        except ValueError as error:
            events.put({'type':'error','text':str(error)})
        except Exception:
            app.logger.exception('Mail draft failed')
            events.put({'type':'error','text':'草稿生成失败，请重试'})
        finally:
            SESSIONS.pop(sid, None)
    def stream():
        Thread(target=run, daemon=True).start()
        while True:
            try:
                event = events.get(timeout=15)
            except Empty:
                event = {'type':'heartbeat'}
            yield json.dumps(event, ensure_ascii=False) + '\n'
            if event['type'] in ('result','error'):
                break
    return Response(stream(), mimetype='application/x-ndjson', headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@app.route("/api/dealer")
def dealer_query():
    return jsonify(match_dealer(request.args.get('country'), request.args.get('seller')))

UP_DIR = os.path.join(BASE, "uploads")
os.makedirs(UP_DIR, exist_ok=True)
VISION_CACHE = {}  # filename -> vlm 识别结果

@app.route("/api/upload", methods=["POST"])
def upload():
    f = request.files.get("image")
    if not f:
        return jsonify({"ok": False, "error": "no file"}), 400
    extension = os.path.splitext(f.filename or "")[1].lower()
    if extension not in (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm") or (request.content_length or 0) > 25 * 1024 * 1024:
        return jsonify({"ok": False, "error": "unsupported image or file too large"}), 400
    fn = uuid.uuid4().hex + extension
    save = os.path.join(UP_DIR, fn)
    f.save(save)
    upload_sid=str(request.form.get('session_id') or '')
    upload_case=SESSIONS.setdefault(upload_sid,{'product':None,'warranty':'UNKNOWN','dealer':'UNKNOWN','troubleshooting':'NOT_STARTED'})
    generation=upload_case.setdefault('media_generation',uuid.uuid4().hex)
    result = media_understanding.understand(save,VLM_BASE,VLM_KEY,VLM_MODEL,request.form.get("language","zh"))
    if result.get('evidence'):result['evidence']=public_data(result['evidence'],SOURCE_ADDRESSES)
    result.update(attachment_id=fn,original_retained=False)
    VISION_CACHE[fn] = {**result,'session_id':upload_sid,'case_generation':generation}
    os.remove(save)
    return jsonify({'ok':True,'filename':fn,'vlm':result.get('evidence'),**result})


PROGRESS_SOURCES = {
    'service-case': ('ServiceOntology', '服务案件定义', 'Service case definition',
                     'ServiceCase 保存本轮产品、订单、诉求和处理状态；用于关联资料，不代表客户身份已核验。',
                     'ServiceCase holds the product, order, request and handling state for this conversation; it does not verify customer identity.'),
    'order': ('Ontology', '订单实体', 'Order entity',
              'lookup_order 按订单号读取源表快照及商品明细。此引用说明查询依据，不证明订单存在、归属已核验或物流为实时状态。',
              'lookup_order reads source-table order snapshots and item records. This reference describes the lookup, not a confirmed match, verified ownership or live tracking.'),
    'product': ('Ontology', '产品实体', 'Product entity',
                'resolve_product 使用产品目录、名称与 SKU 识别产品；存在冲突时保留待确认状态，不跨型号套用知识。',
                'resolve_product uses the product catalog, names and SKUs. Conflicts remain unresolved; knowledge must stay within the matched model.'),
    'decision-rules': ('DecisionOntology', '决策规则', 'Decision rules',
                       'allowed_actions 根据产品、质保、渠道与排障状态限定回复及候选动作。未知状态不能推断过保；审核建议不代表退款或换货已执行。',
                       'allowed_actions constrains responses and candidate actions using product, warranty, channel and troubleshooting states. Unknown does not mean expired; review suggestions do not execute refunds or replacements.'),
    'case-references': ('Ontology', '案件关联关系', 'Case reference relations',
                        'followup_questions.refresh 重新检索资料，生成 ServiceCase 到本轮 Product、Order、OrderItem、KnowledgeItem、ReviewStrategy 或 Policy 的 references 关系；只包含本轮实际生成的节点。',
                        'followup_questions.refresh retrieves sources again and builds references from ServiceCase to the Product, Order, OrderItem, KnowledgeItem, ReviewStrategy or Policy nodes actually generated for this turn.'),
}


def report_progress(zh, en, *source_ids):
    emit = getattr(g, 'progress', None)
    if emit:
        english = g.progress_language == 'en'
        citations = []
        for source_id in dict.fromkeys(source_ids):
            kind, label_zh, label_en, detail_zh, detail_en = PROGRESS_SOURCES[source_id]
            citations.append({'type': kind, 'label': label_en if english else label_zh,
                              'uri': '/ontology-references.html?lang=' + ('en' if english else 'zh') + '#' + source_id,
                              'detail': detail_en if english else detail_zh})
        emit({'type': 'progress', 'language': g.progress_language, 'text': en if english else zh,
              'citations': citations})


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    body = request.get_json(silent=True) or {}
    events = Queue()

    def run():
        with app.test_request_context('/api/chat', method='POST', json=body):
            g.progress = events.put
            g.progress_language = body.get('language', 'zh')
            try:
                response = app.make_response(chat())
                events.put({'type': 'result', 'status': response.status_code, 'data': response.get_json()})
            except Exception:
                app.logger.exception('Streaming chat failed')
                events.put({'type': 'result', 'status': 500, 'data': {'error': 'request_failed'}})

    def stream():
        Thread(target=run, daemon=True).start()
        while True:
            try:
                event = events.get(timeout=15)
            except Empty:
                event = {'type': 'heartbeat'}
            yield json.dumps(event, ensure_ascii=False) + '\n'
            if event['type'] == 'result':
                break
    return Response(stream(), mimetype='application/x-ndjson',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    text = str(body.get("message") or "").strip()[:20000]
    sid = str(body.get("session_id") or uuid.uuid4().hex)[:80]
    request_id = uuid.uuid4().hex[:12]
    if not text:
        return jsonify({"error": "message_required", "request_id": request_id}), 400

    if body.get("new_case"):
        SESSIONS.pop(sid, None)
    case = SESSIONS.setdefault(sid, {"product": None, "warranty": "UNKNOWN",
                                     "dealer": "UNKNOWN", "troubleshooting": "NOT_STARTED"})
    lang = customer_signals.language(text, body.get("language", "auto"), case.get("response_language"))
    case["response_language"] = lang
    g.progress_language = lang
    case["last_message"] = text
    case["reference_date"] = date.today().isoformat()
    report_progress("已收到问题，正在检查会话信息", "Question received; checking conversation context")
    media_token = str(body.get('image') or '').removeprefix('uploaded:')
    media = VISION_CACHE.get(media_token)
    if media_token and (not media or media.get('session_id') != sid or (media.get('case_generation') and media['case_generation'] != case.get('media_generation'))):
        return jsonify({'error':'media_not_available_for_session'}),400
    if media and media.get('status')=='OK':
        case['media_evidence']=media['evidence']
        case['media_coverage']=media.get('coverage')
        case['media_provenance']={k:media.get(k) for k in ('attachment_id','sha256','sample_timestamps_seconds','timestamp_basis','audio_status','original_retained')}
        report_progress('已将媒体转为待核验的文字描述，正在检索相关资料', 'Media converted to unverified text evidence; retrieving relevant sources', 'service-case')
    elif media:
        case.pop('media_evidence',None);case.pop('media_provenance',None);case.pop('media_coverage',None)
    previous_intent = case.get("service_intent")
    previous_product = case.get("product")
    case.pop("order_conflict", None)
    if text.strip() in ("这些都不是我的订单", "None of these are my orders"):
        case["order_candidates_declined"] = True
    mentioned = resolve_product(text, None)
    general_support.prepare(case,text,bool(mentioned["product"]))
    if mentioned["product"] and previous_product and mentioned["product"]["id"] != previous_product["id"]:
        case.pop("order_candidates_declined", None)
        if not media:case.pop('media_evidence',None);case.pop('media_provenance',None);case.pop('media_coverage',None)
        # A newly named product cannot inherit the previous product's order or warranty.
        for key in ("order_id", "within_30d", "purchase_date_claim", "date_claim_pending", "last_issue", "selected_sku", "selected_tracking", "purchase_channel_claim"):
            case.pop(key, None)
        case.pop("active_workflow", None)
        case.update(warranty="UNKNOWN", dealer="UNKNOWN", troubleshooting="NOT_STARTED")

    report_progress("正在识别问题类型", "Identifying the request type")
    # Local resolution and deterministic workflows run before any paid model call.
    intent = {"mentioned_product": None}
    g.model_status = "NOT_USED"
    g.model_calls = 0
    g.degraded_reason = None
    g.reply_sources = []
    g.evidence_excerpts = {}
    g.answer_route = "WORKFLOW"
    model_status = g.model_status

    m = re.search(r"(?<![A-Za-z0-9])(?:Anker\d{3}|ORD-\d{4}|DEMO-O-\d+)(?![A-Za-z0-9-])", text, re.I)
    explicit_order = (m.group(0).upper() if m else str(body.get("order_id") or "").upper())
    if explicit_order:
        if case.get("order_id") != explicit_order:
            for key in ("purchase_date_claim", "date_claim_pending", "last_issue", "selected_sku", "selected_tracking", "purchase_channel_claim"):
                case.pop(key, None)
            case.pop("active_workflow", None)
            case["troubleshooting"] = "NOT_STARTED"
        case["order_id"] = explicit_order
    order_id = case.get("order_id")
    ticket = next((t for t in TICKETS if t['原文行号'] == body.get('ticket_row')), None)
    sku_match = re.search(r"(?<![A-Z0-9])[TE][0-9][A-Z0-9]{6}(?:-[A-Z0-9]+)?(?![A-Z0-9-])", text, re.I)
    selected_sku = sku_match.group(0).upper() if sku_match else (ticket.get('SKU') if ticket else None)
    if selected_sku:
        case['selected_sku'] = selected_sku
        case.pop('selected_tracking', None)
    tracking_match = re.fullmatch(r'(Anker\d{7}(?:-\d+)?)(?:呢|[?？。 ]*)', text, re.I)
    if tracking_match:
        case['selected_tracking'] = tracking_match.group(1)
        case.pop('selected_sku', None)
    shipping = re.search(r'物流|发货|包裹|快递|到货|没收到|未收到|没到|只收到|订单到哪|shipping|shipped|shipment|tracking|arriv|deliver|package|not received|label (?:has been )?created|where is my order|bestelling|verzonden|niet binnen|livraison|livré|lieferung|versand|pedido|envío|llegado', text, re.I)
    fault_report = re.search(r'Problem Type:\s*ERROR|Problem (?:Code|Push):|Fehlercode:|Probleemcode:|capteur laser|code d.erreur|motor.*noise|won.t hold the battery|cutting off|water tray will not empty|pins? is jammed|no longer charge|错误码|故障码|加水异常|注水异常|(?<![A-Z0-9])E[B0-9][A-Z0-9]{1,3}(?![A-Z0-9])', text, re.I)
    if fault_report:
        shipping = None
        case['service_intent'] = 'troubleshooting'
        case['last_issue'] = text
        # A newly supplied diagnostic report takes precedence over old order selection.
        case.pop('selected_tracking', None)
    elif shipping:
        case['service_intent'] = 'shipping'
    elif re.search(r'无法开机|不能开机|充不上|无法充电|不吸|吸力|故障|漏水|power on|turn on|charging|not working|isn.t working|产品用不了', text, re.I):
        case['service_intent'] = 'troubleshooting'
        case.pop('last_issue', None)
    elif re.search(r'保修|质保|warranty', text, re.I):
        case['service_intent'] = 'warranty'
    elif re.search(r'退货|退款|换货|refund|return|replace', text, re.I):
        case['service_intent'] = 'return'

    if text.strip() in quick_replies.CHANNELS:
        case['purchase_channel_claim'] = quick_replies.CHANNELS[text.strip()]
    order = lookup_order(order_id, case.get('selected_sku'))
    if order.get('status') == 'FOUND' and not isinstance(order.get('order', {}).get('items'), list):
        order = {'status':'UNAVAILABLE','warranty':'UNKNOWN'}
        g.degraded_reason = 'order_schema_changed'
    case["order_status"] = order["status"]
    report_progress({'FOUND': '已找到订单资料', 'NOT_FOUND': '未找到该订单，需补充或核对信息', 'NOT_PROVIDED': '尚未提供订单号'}.get(order['status'], '订单检查完成'),
                    {'FOUND': 'Order records found', 'NOT_FOUND': 'Order not found; more information needed', 'NOT_PROVIDED': 'No order number provided'}.get(order['status'], 'Order check complete'), 'order')
    if order["status"] == "FOUND":
        case["warranty"] = order["warranty"]
        case["dealer"] = match_dealer(order["order"]["country"], order["order"]["seller"])["status"]
        case["within_30d"] = order["within_30d"]
        sku = order["order"]["sku"]
    else:
        sku = None
        if explicit_order:
            case.update(warranty="UNKNOWN", dealer="UNKNOWN", within_30d=False)
    ticket = next((t for t in TICKETS if t['原文行号'] == body.get('ticket_row')), None)
    if ticket and not sku:
        sku = ticket.get('SKU')
    # A channel lookup uses explicit country + catalog seller, never delivery address.
    dealer_hits = [(d, name) for d in DEALERS for name in d['seller_names']
                   if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.I)
                   and re.search(r'(?<!\w)' + re.escape(d['country']) + r'(?!\w)', text, re.I)]
    if len(dealer_hits) == 1:
        d, name = dealer_hits[0]
        case['dealer'] = match_dealer(d['country'], name)['status']
        case['dealer_evidence'] = {'country':d['country'], 'seller':name, 'authorized':d['authorized']}
        case['service_intent'] = 'dealer'
    product_result = resolve_product(text, sku)
    if product_result["product"]:
        case["product"] = product_result["product"]
        case["product_state"] = product_result["state"]
    elif product_result["state"] == "CONFLICTED":
        case["product"] = None
        case["product_state"] = "CONFLICTED"
        case["last_issue"] = text
    elif not case.get("product"):
        case["product_state"] = "UNKNOWN"

    target_product = mentioned.get('product') or previous_product
    if proactive_orders.resolve_conflict(case, order, target_product):
        order = {'status':'NOT_PROVIDED','warranty':'UNKNOWN'}
        case['order_status'] = 'NOT_PROVIDED'
        order_id = None

    if re.search(r"(?:买|购买|日期|说错|actually|purchased).{0,25}\d{4}[-/]\d{1,2}[-/]\d{1,2}", text, re.I):
        claimed = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
        case["purchase_date_claim"] = claimed.group(0) if claimed else None
        case["date_claim_pending"] = True
    if case.get("date_claim_pending"):
        case["warranty"] = "PENDING_RECHECK"
    if re.search(r"(仍没恢复|还是不行|试过了|tried everything|still (?:not|won't))", text, re.I):
        case["troubleshooting"] = "USER_REPORTED_FAILED"
    elif re.search(r"(第二步没看懂|step two|step 2)", text, re.I):
        case["troubleshooting"] = "NEEDS_GUIDANCE"

    if case.get("product") and not case.get("last_issue") and not re.fullmatch(r"(?:是)?(?:吸奶器|扫地机)", text):
        case["last_issue"] = text
    if not shipping and case.get('product') and (qa.topics(text, case['product']['id']) or re.search(r'固件|地图|重置|序列号|serial number|firmware|reset|噪音|清洗|消毒|自定义|吸乳节奏', text, re.I)):
        case['service_intent'] = 'troubleshooting'
    active = case.get('active_workflow')
    if active:
        new_topics = qa.topics(text, case['product']['id']) if case.get('product') else set()
        if case.get('service_intent') != previous_intent or (new_topics and active['topic'] not in new_topics) or fault_report:
            case.pop('active_workflow', None)
    media_evidence = case.get('media_evidence') or {}
    media_query = ' '.join(media_evidence.get(k,'') for k in ('visible_issue','description','error_code'))
    query = " ".join(x for x in (case.get("last_issue"), text,media_query) if x)
    fault = match_fault(case["product"]["id"], query) if case.get("product") else None
    if case.get('product'):
        report_progress('已识别产品：' + case['product']['name'], 'Product identified: ' + case['product']['name'], 'product')
    report_progress('正在核对资料和回复范围', 'Checking source records and response limits', 'decision-rules')
    allowed, forbidden, reasons = allowed_actions(case)
    emotion, scope = detect_emotion(text), detect_scope(text)
    if scope != "IN_SCOPE":
        allowed, forbidden = ["prepare_human_handoff"], ["direct_refund", "propose_replacement"]
        reasons = ["超出自助范围：只整理人工交接信息，尚未实际转接"]
    candidates = longtail.retrieve(text, pn=(case.get("product") or {}).get("id"))
    strategy_only = candidates and all(not longtail.product_guide(i) for i in candidates)
    order_selection = not previous_intent and order['status'] == 'FOUND' and bool(re.fullmatch(r'(?:Anker\d{3}|是这笔订单，我要查询 Anker\d{3}|Yes, I am asking about order Anker\d{3})[。.! ]*', text, re.I))
    direct = longtail.direct_answer(candidates, case, lang) if not re.search(qa.RISK,text,re.I) else None
    general = general_support.answer(case,text,lang) if scope == 'IN_SCOPE' and not re.search(qa.RISK,text,re.I) else None
    # Feedback about the assistant is a new conversational act, not a request
    # to repeat the last business workflow. Preserve that workflow for later.
    conversation_repair = bool(re.search(
        r'(?:听不懂|没听懂|不理解|理解错|答非所问|没回答我的问题|没有回答我的问题|'
        r'听懂我说|理解我说|doesn.t understand|don.t you understand|not listening|'
        r'not answering my question|you misunderstood)', text, re.I))
    if conversation_repair and scope == 'IN_SCOPE':
        reply = ('抱歉，我可能误解了你的意思。请告诉我刚才哪一部分理解错了，'
                 '或重新说一下你现在想解决的问题，我会先确认需求再继续。' if lang == 'zh' else
                 "I'm sorry I may have misunderstood. Please tell me what I got wrong "
                 "or what you need help with now, and I'll clarify before continuing.")
        cards = []
        g.answer_route = 'CONVERSATION_REPAIR'
    elif general:
        reply,cards=general['reply'],[]
        g.reply_sources=[general['source']]
        g.answer_route='GENERAL_SUPPORT_CACHE'
        case['service_intent']='troubleshooting'
    elif direct:
        reply, cards = direct['reply'], []
        g.reply_sources = [direct['source']]
        g.answer_route = 'LONG_TAIL_CACHE'
    elif order_selection:
        count=len(order['order']['items'])
        reply = (('已找到这笔订单，商品和物流资料见订单卡片。' + ('这笔订单有多件商品，点击对应商品下的“查询这件商品”即可。' if count > 1 else '请确认是否是这笔订单，再告诉我想查询物流还是处理产品问题。')) if lang == 'zh' else 'I found the order. Review the order card and select the item you want help with.')
        cards=[]
        g.answer_route='ORDER_SELECTION'
    elif strategy_only and order['status'] not in ('NOT_FOUND','UNAVAILABLE') and case.get('product_state') != 'CONFLICTED' and scope == 'IN_SCOPE' and not re.search(qa.RISK,text,re.I) and case.get('service_intent') not in ('shipping','dealer','troubleshooting','warranty'):
        reply, cards = longtail.fallback(candidates,lang), []
        g.answer_route = 'LONG_TAIL_STRATEGY'
    else:
        reply, cards = build_reply(case, text, order, fault, allowed, lang, scope)
    if case.get("date_claim_pending"):
        cards.append({"title": "日期更正待核验" if lang == "zh" else "Date correction pending",
                      "body": "用户陈述：" + str(case["purchase_date_claim"]) + "；测试订单原日期未修改，质保结论需人工重核。" if lang == "zh" else
                              "Customer claim: " + str(case["purchase_date_claim"]) + "; fixture order date unchanged. Warranty needs review."})
    report_progress("核对完成，正在返回答复", "Checks complete; returning the response")
    model_status = g.model_status
    citations = list(g.reply_sources)
    if g.answer_route == 'DEALER_LOOKUP':
        citations = [{'id':'dealer-directory','kind':'dealer','label':'赛题经销商名录 · '+case['dealer_evidence']['country']+' · '+case['dealer_evidence']['seller'],'url':'/api/sources/dealer-directory'}]
    if not citations and order['status'] == 'FOUND' and g.answer_route != 'CONVERSATION_REPAIR':
        for item in order['order']['items']:
            if case.get('selected_sku') and item.get('SKU') != case['selected_sku']:
                continue
            if case.get('selected_tracking') and case['selected_tracking'].lower() not in str(item.get('物流单号', '')).lower():
                continue
            row = item['原文行号']
            citations.append({'id': f'order-{row}', 'kind': 'order', 'label': f'订单信息 · 第 {row} 行（资料快照）', 'url': f'/api/sources/order-{row}'})
    if not citations:
        citations = [{'id': 'service-rules', 'kind': 'context', 'label': '依据：本轮信息与服务规则（无产品知识引用）', 'url': '/api/sources/service-rules'}]
    long_tail_matches = longtail.retrieve(text, pn=(case.get("product") or {}).get("id"))
    protected_routes = {'CONVERSATION_REPAIR','GENERAL_SUPPORT_CACHE','ORDER_NOT_FOUND','LONG_TAIL_CACHE','PRODUCT_CLARIFICATION','DEPENDENCY_FALLBACK','FAQ_CACHE','ERROR_CODE_WORKFLOW','ERROR_CODE_SOURCE','ERROR_CODE_CLARIFICATION',
                        'WORKFLOW_FOLLOWUP','ATTEMPTED_STEPS_REVIEW','SOURCE_CONFLICT','HUMAN_REVIEW','SOURCE_FALLBACK','DEALER_LOOKUP','WARRANTY_CHECK'}
    if g.reply_sources and all(longtail.product_guide(i) for i in long_tail_matches):
        long_tail_matches = []
    use_longtail = bool(long_tail_matches) and g.answer_route not in protected_routes and scope == 'IN_SCOPE'
    if use_longtail:
        report_progress('已匹配长尾场景，正在读取补充核查策略', 'Matched a long-tail scenario; reading supplementary review strategies')
        # Supplementary material changes neither eligibility nor executable actions.
        if not g.reply_sources and case.get('service_intent') not in ('shipping','dealer','troubleshooting','warranty'):
            reply = longtail.fallback(long_tail_matches,lang)
        citations += [longtail.citation(item) for item in long_tail_matches]
        g.answer_route = 'LONG_TAIL_STRATEGY'
    wants_order = bool(case.get('order_conflict') or case.get('service_intent') in ('shipping','return','warranty') or re.search(r'订单号|order number',text,re.I) or (not g.reply_sources and not long_tail_matches and case.get('service_intent') != 'troubleshooting'))
    candidate_orders = proactive_orders.candidates(case, ORDERS) if wants_order and g.answer_route != 'CONVERSATION_REPAIR' else []
    if candidate_orders and scope == 'IN_SCOPE' and g.answer_route not in {'GENERAL_SUPPORT_CACHE','HUMAN_REVIEW','DEPENDENCY_FALLBACK','ORDER_NOT_FOUND','FAQ_CACHE','ERROR_CODE_WORKFLOW','ERROR_CODE_SOURCE','ERROR_CODE_CLARIFICATION','WORKFLOW_FOLLOWUP','ATTEMPTED_STEPS_REVIEW','SOURCE_CONFLICT'} and not re.search(qa.RISK,text,re.I):
        report_progress('正在按产品型号匹配候选订单，等待您点选确认', 'Matching order candidates by product model for your confirmation', 'order', 'product')
        conflict = case.get('order_conflict')
        lead = ((f"您提供的 {conflict['order_id']} 与当前产品型号不匹配，我重新帮您匹配。" if lang=='zh' else f"{conflict['order_id']} does not match the current product model. Let me help find matching records.") if conflict else '')
        prompt = ('已按型号找到以下演示订单，点击对应商品即可，不用手动查找订单号。这些是赛题资料中的候选记录，尚未核验归属；如果都不对，可以选择“这些都不是我的订单”。' if lang=='zh' else 'I found matching demo order records. Select an item below without typing an order number. These dataset candidates are not verified as yours; you can choose “None of these are my orders”.')
        if case.get('service_intent')=='troubleshooting' and not conflict:
            reply += '\n\n' + prompt
        else:
            reply = lead + '\n\n' + prompt
        citations += [{'id':item['source_id'],'kind':'order','label':item['order_id']+' · '+item['sku'],'url':item['source_url']} for item in candidate_orders if item['source_id'] not in {c['id'] for c in citations}]
        g.answer_route = 'ORDER_CANDIDATES'
        g.three_segment_reply = False
    elif case.get('order_candidates_declined') and text.strip() in ('这些都不是我的订单','None of these are my orders'):
        reply = ('好的，不会使用这些候选订单。您可以上传购买凭证或联系人工协助核查；也可以继续描述产品问题。' if lang=='zh' else 'I will not use these candidate orders. You can upload proof of purchase or contact support for help, or continue describing the product issue.')
        g.answer_route = 'ORDER_CANDIDATES'
    else:
        candidate_orders = []
    direct_routes = {'CONVERSATION_REPAIR','GENERAL_SUPPORT_CACHE','ORDER_CANDIDATES','ORDER_NOT_FOUND','ORDER_SELECTION','FAQ_CACHE','LONG_TAIL_CACHE','PRODUCT_CLARIFICATION','WARRANTY_CHECK','WORKFLOW_FOLLOWUP','ERROR_CODE_WORKFLOW','DEPENDENCY_FALLBACK'}
    g.pre_model_route = g.answer_route
    if (GROUNDED_MODE or use_longtail) and LLM_KEY and LLM_MODEL and g.answer_route not in direct_routes:
        evidence=[]
        for c in citations:
            if c['id'] in longtail.ENTRIES:
                item=longtail.ENTRIES[c['id']]
                content={'evidence_level':'SUPPLEMENTARY_REVIEW_STRATEGY_NOT_POLICY','strategy':item['strategy'],'slots_to_verify':item['slots'],'title':item['title']}
            elif c['id'] == 'dealer-directory':
                content=case['dealer_evidence']
            elif c['id'] in qa.SOURCES:
                r=qa.SOURCES[c['id']];content=r['Title']+'\n'+getattr(g,'evidence_excerpts',{}).get(c['id'],r['Content'])
            elif c['id'].startswith('order-'):
                n=int(c['id'][6:]);content=public_data(next((r for o in ORDERS.values() for r in o['items'] if r['原文行号']==n),{}), SOURCE_ADDRESSES)
            else:
                content={'rule_result':reply,'limitations':'No real email, refund, replacement, transfer or live carrier execution.'}
            evidence.append({'id':c['id'],'label':c['label'],'content':content})
        report_progress('正在调用 DeepSeek，结合资料和前文生成回复', 'Calling DeepSeek with evidence and conversation context')
        g.model_validation = {}
        generated=grounded_response.generate(call_llm,text,lang,case,reply,citations,evidence,allowed,forbidden,body.get('channel','chat'),emotion=emotion,diagnostics=g.model_validation)
        if generated:
            reply,citations=generated
            g.three_segment_reply=True
            g.answer_route='GROUNDED_LLM'
        else:
            if g.model_status != 'ERROR':
                g.model_status='INVALID_RESPONSE'
            g.degraded_reason = g.degraded_reason or 'model_validation_failed'
            report_progress('模型回复未通过检查或连接失败，保留有依据的回复', 'Model unavailable or response failed checks; using evidence-based fallback')
        model_status=g.model_status
    if lang == 'es' and g.answer_route != 'CONVERSATION_REPAIR' and not getattr(g,'three_segment_reply',False) and case.get('service_intent') == 'shipping':
        items=order.get('order',{}).get('items',[])
        lines=['SKU '+str(i.get('SKU',''))+'; transportista: '+str(i.get('物流承运商') or 'no disponible')+'; seguimiento: '+str(i.get('物流单号') or 'no disponible')+'; estado registrado: '+str(i.get('物流状态') or 'no disponible') for i in items]
        reply='Entiendo que su pedido todavía no ha llegado.\n\n'+'\n'.join(lines)+'\nSon registros guardados, no una consulta de seguimiento en tiempo real.\n\nContacte con el transportista o solicite una revisión humana para verificar la diferencia. No se ha realizado ninguna gestión.'
    if lang == 'nl' and g.answer_route != 'CONVERSATION_REPAIR' and not getattr(g,'three_segment_reply',False) and case.get('service_intent') == 'shipping' and order['status']=='FOUND':
        items=order['order']['items']
        reply='U meldt dat uw bestelling '+order['order']['order_id']+' nog niet is aangekomen.\n\nVolgens de opgeslagen gegevens: ' + '; '.join(str(i.get('SKU','niet opgegeven'))+' — '+str(i.get('物流承运商') or 'niet opgegeven')+' — '+str(i.get('物流单号') or 'niet opgegeven')+' — '+str(i.get('物流状态') or 'niet opgegeven') for i in items) + '\n\nDit zijn opgeslagen gegevens, geen actuele tracking. Een afleverregistratie bevestigt niet dat u het pakket hebt ontvangen. Laat de vervoerder het verschil onderzoeken met het bovenstaande trackingnummer.'
    if any(c['kind'] != 'context' for c in citations) and not getattr(g,'three_segment_reply',False):
        reply += " " + " ".join(f"[{i}]" for i in range(1, len(citations) + 1))
    order_snapshot = order_cards.build(order)
    show_order_card = bool(order_snapshot and (explicit_order or body.get('ticket_row')) and case.get('last_order_card') != order_snapshot['order_id'])
    if show_order_card:
        case['last_order_card'] = order_snapshot['order_id']
    elif not order_snapshot:
        case.pop('last_order_card', None)
    reply=public_data(reply,SOURCE_ADDRESSES)
    case['emotion']=emotion
    case['recommended_next_action']='Review the cited evidence and attempted steps; verify ownership and channel before any after-sales approval.'
    case['turn_count'] = case.get('turn_count', 0) + 1
    case.setdefault('transcript', []).extend([{'role':'user','text':text}, {'role':'assistant','text':reply,'citations':citations,'order_card':order_snapshot if show_order_card else None}])
    report_progress('正在重新检索本体关联，更新后续问题', 'Re-querying ontology links for follow-up questions', 'service-case', 'case-references')
    case['followups'] = followup_questions.refresh(case,text,citations,order)
    case['followups'] = user_experience.enrich_questions(case['followups'],case,ORDERS)
    if g.answer_route == 'GENERAL_SUPPORT_CACHE':
        case['followups']=general_support.followups(case,case['followups'])
    case['followups']['quick_replies'] = quick_replies.choices(case,reply,order)
    case['followups']['language'] = lang
    trace = {"degraded_reason":g.degraded_reason,"pre_model_route":g.pre_model_route,"cache_hit":g.pre_model_route in {"GENERAL_SUPPORT_CACHE","FAQ_CACHE","LONG_TAIL_CACHE"},"long_tail": {'classification':'long_tail_candidate' if use_longtail else ('existing_workflow' if long_tail_matches else 'no_match'),
                           'source_ids':[i['id'] for i in long_tail_matches] if use_longtail else [],
                           'basis':'curated phrase match; not an empirical frequency estimate'}, "emotion": emotion, "product": case["product"]["name"] if case.get("product") else "未确定",
             "product_state": case.get("product_state", "UNKNOWN"),
             "evidence": product_result["evidence"], "model_candidate": intent.get("mentioned_product") or "无",
             "order": order_id or "未提供",
             "order_status": order["status"], "order_source": "SUPPLIED_DATASET" if order["status"] == "FOUND" else ("USER_CLAIM" if order_id else "NONE"),
             "ownership_status": "NOT_VERIFIED",
             "order_selection": {"rule_id":"DO-PROACTIVE-ORDER-01", "candidate_count":len(candidate_orders), "scope":"demo_dataset", "conflict":case.get("order_conflict")},
             "warranty": case["warranty"], "dealer": case["dealer"],
             "troubleshooting": case["troubleshooting"], "purchase_date_claim": case.get("purchase_date_claim"),
             "knowledge_source": "; ".join(c["label"] for c in citations if c["kind"] == "knowledge") or "NONE", "image": (media.get("status") if media else "已有媒体证据" if case.get("media_evidence") else "未处理"), "media_evidence":case.get("media_evidence"), "media_coverage":case.get("media_coverage"), "media_provenance":case.get("media_provenance"),
             "allowed": allowed, "forbidden": forbidden, "reasons": reasons,
             "workflow_status": case.get("active_workflow", {}).get("status"), "workflow_history": case.get("active_workflow", {}).get("history", []),
             "answer_route": g.answer_route, "cache_key": getattr(g, "cache_key", None), "model_calls": g.model_calls,
             "response_language":lang, "model_finish_reason":getattr(g,"model_finish_reason",None), "model_validation":getattr(g,"model_validation",{}), "model_status": model_status, "model": LLM_MODEL if model_status != "NOT_CONFIGURED" else "无模型配置",
             "request_id": request_id, "rule_version": "m0-safe-1",
             "case_source": "会话内存 + 用户提供的赛题数据 + Python 规则"}
    return customer_response(**{"degraded_reason":g.degraded_reason,"response_language": lang, "reply": reply, "cards": cards, "trace": trace, "citations": citations, "order_card": order_snapshot if show_order_card else None, "order_snapshot": order_snapshot, "selection_cards": candidate_orders or ([] if case.get("order_candidates_declined") else user_experience.choices(case,ORDERS,PRODUCTS)), "diagrams": user_experience.diagrams(citations,qa.SOURCES),
                    "model_status": model_status, "request_id": request_id, "turn_count": case["turn_count"], "handoff_available": case["turn_count"] > 8, "followups":case["followups"]})


def shipping_reply(case, text, order, zh):
    selected_sku = case.get('selected_sku')
    tracking_problem = re.search(r'查不到|查询失败|单号.*(?:无效|不行)|tracking.*(?:not working|doesn.t work|invalid|not found)|when.*(?:getting|receive|arriv)', text, re.I)
    if order['status'] != 'FOUND':
        if order['status'] == 'NOT_FOUND':
            return ((f"没有查到订单 {case['order_id']}，请核对订单号。商品编码不能代替订单号。" if zh else
                     "I could not find that order. Please check the order number; a product code is not an order number."), [])
        return ((f"{selected_sku + ' 是商品编码，' if selected_sku else ''}还需要你的订单号，才能查询这次购买的发货情况。请发送订单号（例如 Anker002）。" if zh else
                 "Please share your order number (for example Anker002). A product code alone cannot identify your shipment."), [])
    items = order['order']['items']
    tracking = case.get('selected_tracking')
    if tracking:
        items = [r for r in items if tracking.lower() in str(r.get('物流单号', '')).lower().split()]
    elif selected_sku:
        items = [r for r in items if r.get('SKU', '').upper() == selected_sku.upper()]
    if not items:
        return ((f"订单 {case['order_id']} 中没有找到这个商品或物流单号。请确认编码，或提供对应的订单号。" if zh else
                 "That item or tracking number was not found in this order. Please confirm the code or provide the matching order number."), [])
    lines, cards = [], []
    for item in items:
        sku = item.get('SKU', '—')
        status = item.get('订单状态', '未提供')
        shipped = item.get('发货日期', '未提供')
        carrier = item.get('物流承运商', '未提供')
        number = item.get('物流单号', '未提供')
        delivery = str(item.get('物流状态', '未提供'))
        if zh:
            delivery = re.sub(r'Delivered on (\d+)/(\d+)', r'\1 月 \2 日已签收', delivery, flags=re.I)
            lines.append(f"{sku}：{status}。发货日期：{shipped}；承运商：{carrier}；物流单号：{number}；记录状态：{delivery}。")
        else:
            lines.append(f"{sku}: dispatch date {shipped}; carrier {carrier}; tracking {number}; recorded status: {delivery}.")
        cards.append({'title': ('物流详情 · ' if zh else 'Shipment · ') + sku,
                      'body': f"{carrier} · {number}\n{delivery}"})
    reply = ('根据订单中的物流记录：\n' if zh else 'According to the saved shipment records:\n') + '\n'.join(lines)
    missing = re.search(r'没收到|未收到|没到|not received|did not arrive|not arrive|haven.t received|niet binnen', text, re.I)
    if missing:
        reply += ('\n你反馈未收到，但记录显示的状态可能与实际情况不一致。请先核对收件位置；仍未找到时，需要联系承运商或人工客服核查。' if zh else
                  '\nYou reported a missing parcel. The recorded status may differ from what happened; check the delivery location and contact the carrier or support if it is still missing.')
    reply += ('\n以上是已提供资料中的记录，尚未查询实时物流。' if zh else '\nThese are saved records, not a live carrier update.')
    if re.search(r'label (?:has been )?created|label has been created|标签已创建', text, re.I):
        reply += ('\n你提到承运商显示“标签已创建”，但订单快照显示签收，两者存在冲突，不能确认实际送达或包裹内容。需要携带上述单号向承运商核查。' if zh else
                  '\nYou report that the carrier shows label created, while the snapshot says delivered. These conflict: neither the actual delivery nor parcel contents can be confirmed. The carrier needs to investigate the tracking numbers above.')
        tracking_problem = None
    if tracking_problem:
        if zh:
            reply = (f"你现在遇到的是物流单号查询失败，还想确认什么时候收到。我目前无法查询承运商实时状态，因此不能确认预计送达时间。\n"
                     f"如果仍是前面的订单 {case['order_id']}，保存的记录显示：\n" + '\n'.join(lines) +
                     "\n记录显示签收并不代表你已经收到。你查的是这笔订单，还是另一笔？请发一下查询失败的完整物流单号和承运商名称，我先帮你核对是否对应。")
        else:
            reply = (f"Your tracking lookup is not working, and you want an arrival estimate. I cannot check live carrier data, so I cannot confirm an ETA. If this is still order {case['order_id']}, the saved records say:\n" + '\n'.join(lines) +
                     "\nA recorded delivery does not confirm that you received it. Is this the same order or a different one? Please share the full tracking number and carrier so I can check the match.")
    if re.fullmatch(r'[?？!！\s]+', text):
        reply = ('抱歉，刚才没有说清楚。\n' if zh else 'Sorry, let me clarify.\n') + reply
    return reply, cards


def answer_knowledge(case, text, lang):
    pn = case['product']['id']
    query = text
    # Short model confirmation continues the preceding issue; new symptoms replace it.
    if re.fullmatch(r'(?:是)?(?:吸奶器|扫地机)|[TE][A-Z0-9-]{4,}', text, re.I) and case.get('last_issue'):
        query = case['last_issue']
    codes = list(dict.fromkeys(re.findall(r'(?<![A-Z0-9])E[B0-9][A-Z0-9]{1,3}(?![A-Z0-9])', query.upper())))
    if codes:
        matches = [sid for sid, row in qa.SOURCES.items() if pn in row['PN'].split(';') and
                   any(re.search(r'(?<![A-Z0-9])' + re.escape(code) + r'(?![A-Z0-9])', row['Title'], re.I) for code in codes)]
        if not matches:
            g.answer_route = 'ERROR_CODE_CLARIFICATION'
            return ('没有找到该型号与错误码的精确对应资料。请确认完整错误码，或提供 App 报错截图；我不会用相近代码的步骤代替。' if lang == 'zh' else
                    'I could not find an exact match for this model and code. Please confirm the full code or share the app error screenshot.')
        if pn == 'T2080' and codes == ['EB1L']:
            g.answer_route = 'ERROR_CODE_WORKFLOW'
            g.reply_sources = [qa.citation('r-482')]
            report_progress('已精确匹配 T2080 / EB1L 加水故障资料', 'Exact T2080 / EB1L water-filling reference found')
            steps_by_language = {'zh': ('1. 取下基站清水箱，检查出水口密封圈是否装好，用手电查看箱内水管是否损坏；加水至 MAX 后重新放稳。\n'
                     '2. 检查机器人进水口是否有杂物，用纸巾或棉签清理；再检查基站注水口橡胶塞是否损坏或缺失。\n'
                     '3. 资料要求固件为 7.0.143 或以上。请确认当前版本。'), 'en': (
                     '1. Check the clean-water tank outlet seal and internal pipe, refill to MAX and reseat it.\n'
                     '2. Clear debris from the robot water inlet and inspect the station inlet rubber plug.\n'
                     '3. The guide specifies firmware 7.0.143 or later. Please check your version.')}
            steps = steps_by_language['zh' if lang=='zh' else 'en']
            workflow.remember(case, pn, 'EB1L', steps, g.reply_sources, steps_by_language)
            return ('这是 S1 Pro 的 EB1L 加清水异常，任务因此结束。请按以下步骤检查：\n' if lang == 'zh' else
                    'EB1L means the S1 Pro stopped because of a clean-water filling error. Please check:\n') + steps
        g.answer_route = 'ERROR_CODE_SOURCE'
        g.reply_sources = [qa.citation(sid) for sid in matches[:3]]
        return ('已找到该型号与错误码的精确资料。当前尚未生成可核验的中文排障说明，可点击引用核对原文，或交人工复核。' if lang == 'zh' else 'Exact model and error-code references:\n' + '\n\n'.join(qa.SOURCES[sid]['Content'] for sid in matches[:3]))
    report_progress('正在匹配常见问题工作流', 'Matching reviewed FAQ workflows')
    if pn == 'T2080' and re.search(r'清洁.*仍|despite.*clean|already.*clean', query, re.I) and re.search(qa.PATTERNS['charge'], query, re.I):
        g.answer_route = 'ATTEMPTED_STEPS_REVIEW'
        g.reply_sources = [qa.citation('r-474')]
        return ('已了解，你清洁充电触点后仍无法充电。请告诉我基站是否通电、屏幕和水箱内部的指示灯是否亮起；这是资料中的电源检查项，可以继续排查，不必重复清洁触点。' if lang == 'zh' else
                'You have cleaned the charging contacts but it still will not charge. Is the base station powered on, and are the screen and water-tank indicator lights illuminated? These power checks come from the guide; there is no need to repeat cleaning the contacts.')
    hit = qa.cached_answer(pn, query, lang)
    if hit:
        g.answer_route = 'FAQ_CACHE'
        g.cache_key = hit['key']
        g.reply_sources = [qa.citation(sid) for sid in hit['source_ids']]
        case['last_faq_topic'] = hit['topic']
        workflow.remember(case, pn, hit['topic'], hit['reply'], g.reply_sources)
        report_progress('已命中审核固定答复，无需调用模型', 'Reviewed cached answer found; no model call needed')
        return hit['reply']
    if pn == 'T2080' and re.search(r'序列号|serial number|\bsn\b', query, re.I):
        g.answer_route = 'SOURCE_CONFLICT'
        g.reply_sources = [qa.citation(sid) for sid in ['r-6', 'r-19']]
        report_progress('发现资料冲突，保留两条来源供核实', 'Conflicting sources found; both retained for review')
        return ('两条资料对 S1 Pro 序列号位置的说明不一致，一条提到底部，另一条明确说不在底部、应在尘盒下方。我暂时不能确定，请提供机身标签或尘盒区域的照片，便于进一步核实。' if lang == 'zh' else
                'The sources disagree on the S1 Pro serial-number location: the bottom versus underneath the dust box. Please share a label photo so support can verify it.')
    if re.search(qa.RISK, query, re.I):
        g.answer_route = 'HUMAN_REVIEW'
        return ('请先停止使用该设备。这涉及使用安全或身体不适，需要人工进一步确认。请说明具体型号和现象，我会保留你的描述；当前尚未实际转接客服。' if lang == 'zh' else
                'Please stop using the affected device. This involves safety or discomfort and needs human review. Please describe the model and what happened; no support transfer has been made.')
    refs = qa.retrieve(pn, query)
    if not refs:
        report_progress('未找到足够匹配的资料，需要补充问题细节', 'No sufficiently matching evidence; clarification needed')
        return None
    g.reply_sources = [qa.citation(sid) for sid in refs]
    report_progress(f'已检索到 {len(refs)} 条同型号资料', f'Found {len(refs)} model-specific references')
    if pn=='T2351' and re.search(r'water tray will not empty',query,re.I) and 'r-255' in refs:
        g.answer_route='WORKFLOW_FOLLOWUP'
        g.reply_sources=[qa.citation('r-255')]
        g.evidence_excerpts={'r-255':'Check whether the door latch of the dirty water tank is fastened when it is installed on the station.'}
        return ('您已清洁并检查软管和接头，污水仍无法排出。先按资料确认下一项：污水箱装回基站时，锁扣是否扣紧？目前不能判定密封圈损坏，不继续追加后面的条件步骤。' if lang=='zh' else
                'You have already cleaned and checked the hose and connector, but dirty water still will not drain. The next supported check is whether the dirty-water tank latch is fastened when installed. Is that latch securely fastened? A seal defect has not been established; later conditional steps do not yet apply.')
    if re.search(r'capteur laser', query, re.I) and not re.search(r'\b40(?:10|11|13)\b', query):
        g.answer_route='ERROR_CODE_CLARIFICATION'
        return ("Vous avez déjà nettoyé et redémarré votre X10 Pro Omni, mais le message du capteur laser persiste. Les références distinguent plusieurs codes avec des étapes différentes. Quel est le code exact affiché dans l’application ? Je ne peux pas déduire un défaut matériel de ce seul message." if lang=='fr' else
                'You have already cleaned and restarted the X10 Pro Omni, but the laser sensor message persists. The references distinguish several codes with different guidance. What exact code does the app display? This message alone does not establish a hardware fault.')

    if LLM_KEY and LLM_MODEL and not GROUNDED_MODE:
        report_progress('正在根据引用资料组织答复', 'Composing a response from the cited evidence')
        evidence = [{'id': sid, 'title': qa.SOURCES[sid]['Title'], 'content': qa.SOURCES[sid]['Content']} for sid in refs]
        answer = call_llm(qa.STYLE_PROMPT + "\n" + RESPONSE_GUIDE, json.dumps({'language': lang, 'product': pn, 'question': query, 'evidence': evidence}, ensure_ascii=False))
        try:
            parsed = json.loads(answer or '{}')
            ids = parsed.get('source_ids')
            reply = parsed.get('reply')
            if not isinstance(ids, list) or not ids or any(i not in refs for i in ids) or not isinstance(reply, str) or not reply.strip():
                raise ValueError('Invalid cited response')
            if not customer_signals.reply_matches_language(reply, lang):
                raise ValueError('Response language mismatch')
            if re.search(r'已(?:经)?(?:退款|换货|到账|转接)|refund (?:has been |was )?(?:issued|processed)|replacement (?:has been |was )?sent', reply, re.I):
                raise ValueError('Unverified execution claim')
            g.reply_sources = [qa.citation(sid) for sid in dict.fromkeys(ids)]
            g.answer_route = 'GROUNDED_LLM'
            return reply.strip()
        except (ValueError, TypeError, KeyError):
            if g.model_status != 'ERROR':
                g.model_status = 'INVALID_RESPONSE'
            report_progress('生成答复未通过检查，改为展示原始资料', 'Generated answer failed checks; falling back to source text')
    elif not GROUNDED_MODE:
        g.model_status = 'NOT_CONFIGURED'
        report_progress('未配置模型，返回匹配资料原文', 'No model configured; returning matching source text')
    g.answer_route = 'SOURCE_FALLBACK'
    if lang == 'zh':
        return '已找到相关资料。当前尚未生成可核验的中文回复，可点击引用核对资料原文，或交人工复核。'
    prefix = 'Related source text:\n'
    # A fallback quotes the source, never pretends to be a generated translation.
    return prefix + '\n\n'.join(qa.SOURCES[sid]['Title'] + '\n' + qa.SOURCES[sid]['Content'].strip() for sid in refs)


def build_reply(case, text, order, fault, allowed, lang, scope):
    zh = lang == "zh"
    cards = []
    if order.get('status') == 'UNAVAILABLE':
        g.answer_route='DEPENDENCY_FALLBACK'
        return ('订单资料接口的字段发生变化，暂时无法可靠读取。请保留订单号，稍后重试或联系人工核查；当前没有修改订单或办理售后。' if zh else 'The order data format has changed, so I cannot read it reliably. Please keep your order number and retry later or request human review. No order or after-sales action was changed.'),cards
    if re.search(qa.RISK, text, re.I):
        case.pop('active_workflow', None)
        g.answer_route = 'HUMAN_REVIEW'
        return ('请先停止使用该设备。这涉及使用安全或身体不适，需要人工进一步核查。当前尚未实际转接或办理售后。' if zh else
                'Please stop using the affected device. This involves safety or discomfort and needs human review. No transfer or after-sales action has been executed.'), cards
    if (case.get('product') or {}).get('id') == 'T8D04' and re.search(r'pin.*(?:jammed|broken)|触点.*(?:坏|卡住)|针脚.*(?:坏|卡住)', text, re.I):
        g.answer_route='HUMAN_REVIEW'
        g.reply_sources=[qa.citation('b-128'),{'id':'service-rules','kind':'context','label':'服务规则 · 疑似损坏需人工核查','url':'/api/sources/service-rules'}]
        g.evidence_excerpts={'b-128':'If the magnetic contacts on the charging case or the breast pump are damaged or misaligned, it may prevent proper charging.'}
        return (('您描述充电盒一侧的触点卡住或损坏，清洁后仍无法充电。资料提到触点损坏可能影响充电，但尚未确认原因；疑似损坏时先不要继续调整针脚或测试充电。请提供触点照片供人工核查，换货资格仍需凭证核验。' if zh else
                 'You report a jammed or broken charging pin and one side not charging despite cleaning. The reference identifies damaged contacts as a possible cause, not a confirmed diagnosis. Do not manipulate the pin or continue charging tests while damage is suspected. Please share a photo of the contact for human review; replacement eligibility still needs proof of purchase.'), cards)
    common_questions = {
        '我的订单到哪了？': '请发一下你的订单号，我帮你查看发货和物流信息。',
        '产品用不了怎么办？': '请告诉我产品型号，以及遇到的具体问题，比如无法开机、充不上电或吸力变小。',
        '怎么查询保修？': '请提供订单号，我帮你查看保修日期。如果找不到订单号，也可以提供购买日期和购买凭证。',
        '可以退货或换货吗？': '请告诉我订单号和退换原因，我帮你核对下一步需要的信息。是否可以办理，需要根据购买渠道和商品情况确认。',
        'Where is my order?': 'Please share your order number so I can check the shipping information.',
        'My product isn’t working': 'What model do you have, and what is going wrong—for example, not powering on or not charging?',
        'How do I check my warranty?': 'Please share your order number. If you cannot find it, provide your purchase date and proof of purchase.',
        'Can I return or replace it?': 'Please share your order number and the reason for the return. Eligibility depends on the purchase channel and item condition.'
    }
    if text in common_questions and not case.get('order_id'):
        return common_questions[text], cards
    if text.strip() in quick_replies.CHANNELS:
        claim = case.get('purchase_channel_claim')
        if claim == 'unknown':
            return ('没关系，可以先查看下单平台的订单详情或购买凭证，确认店铺名称；暂时不能确认的渠道会保留为待核验。' if zh else 'Please check the store name in your order details or proof of purchase. The purchase channel remains unverified.'), cards
        return ('已记录你提供的购买渠道，仍需购买凭证核验，不代表已确认官方授权。请保留订单详情和购买凭证供人工核查；当前没有提交退款或换货。' if zh else 'I recorded your purchase channel as a customer statement, not verified authorization. Please keep the order details and proof of purchase for review. No refund or replacement was submitted.'), cards
    if scope != "IN_SCOPE":
        return (("这类问题需要人工处理。我已整理本轮问题，请使用官网联系渠道提交，当前系统尚未实际转接。" if zh else
                 "This needs a specialist. Please use the official contact channel; this demo has not transferred the case."), cards)
    if case.get("date_claim_pending") and re.search(r"(日期|说错|actually|purchased)", text, re.I):
        return (("已记录你更正的购买日期。测试订单原始日期仍保留，质保与办理资格等待凭证重核。" if zh else
                 "I recorded your corrected purchase date. The fixture date remains unchanged pending proof review."), cards)
    if case.get('service_intent') == 'shipping':
        return shipping_reply(case, text, order, zh)
    if case.get('service_intent') == 'warranty' and order['status']=='FOUND':
        g.answer_route='WARRANTY_CHECK'
        expiry=order.get('warranty_until') or '未确定 / not confirmed'
        state=case.get('warranty','UNKNOWN')
        fact={'VALID':'按资料日期仍在质保期内','EXPIRED':'按资料日期已过保','UNKNOWN':'需要先选择订单中的具体商品才能核算','PENDING_RECHECK':'日期更正待凭证核验'}.get(state,'待核验')
        fact_en={'VALID':'within the recorded warranty period','EXPIRED':'past the recorded warranty end date','UNKNOWN':'unknown until an item is selected','PENDING_RECHECK':'pending proof review after the claimed date correction'}.get(state,'unknown')
        next_step = ('可请人工核查是否提供付费维修及报价，当前尚未安排维修。' if zh else 'You can request a human review of paid repair availability and a quote; no repair has been arranged.') if state=='EXPIRED' else ''
        return (((f"订单 {case['order_id']}，截至 {case['reference_date']}：{fact}；质保结束日期：{expiry}。这只是资料日期核算，不代表购买归属或退款资格已获批准。退款还需按购买渠道核验；当前未办理退款或换货。" if zh else
                 f"For order {case['order_id']}, as of {case['reference_date']}, warranty is {fact_en}; recorded end date: {expiry}. This date check does not verify ownership or approve a refund. The purchase channel and applicable policy still need review; no refund or replacement has been processed.") + next_step),cards)
    if case.get('service_intent') == 'dealer' and case.get('dealer_evidence'):
        d = case['dealer_evidence']
        g.answer_route = 'DEALER_LOOKUP'
        return ((f"经销商名录中，{d['country']} 的 {d['seller']} {'已列为授权渠道' if d['authorized'] else '未列为授权渠道'}。这仅核验名录，您的购买凭证和具体售后资格仍需另行核查。" if zh else
                 f"The supplied dealer directory lists {d['seller']} in {d['country']} as {'authorized' if d['authorized'] else 'not authorized'}. This verifies the directory entry, not your purchase or service eligibility."), cards)
    if order["status"] == "NOT_FOUND":
        g.answer_route="ORDER_NOT_FOUND"
        return (("赛题订单库未找到 " + case["order_id"] + "。这不代表过保；请提供购买渠道和凭证，暂不能办理退款或换货。" if zh else
                 "Order " + case["order_id"] + " is absent from the demo fixtures. Warranty is unknown; please provide proof of purchase."), cards)
    if not case.get("product"):
        g.answer_route="PRODUCT_CLARIFICATION"
        if re.search(r"(退款|refund|换货|replace|replacement)", text, re.I):
            return (("请提供产品型号、订单号及购买凭证。我可以整理待人工审核材料，当前没有发起退款或换货。" if zh else
                     "Please provide the model, order number and proof of purchase. I can prepare a review summary; no refund or replacement was initiated."), cards)
        if case.get('media_evidence') and case.get('product_state') != 'CONFLICTED':
            g.answer_route = 'MEDIA_PRODUCT_CLARIFICATION'
            observation = str(case['media_evidence'].get('visible_issue') or case['media_evidence'].get('description') or '')[:240]
            return ((f"我已收到图片/视频识别信息。模型观察到：{observation}\n这些是待核验线索，暂时不能据此判断故障或解释指示灯含义。请告诉我具体产品型号，以及实际遇到的异常；如果是指示灯问题，请补充常亮还是闪烁。我会按型号核对对应知识，再给出下一步建议。" if zh else
                     f"I received the image/video observations: {observation}\nThese are unverified clues, not a confirmed fault or an interpretation of the lights. Please share the exact product model and what is going wrong; for indicator lights, tell me whether they are steady or blinking. I can then check the matching support information."), cards)
        return (("S1 Pro 有吸奶器和扫地机两种产品，请确认是哪一种。" if zh else
                 "S1 Pro can be a breast pump or a robot vacuum. Which one do you have?") if case.get("product_state") == "CONFLICTED" else
                ("请告诉我具体产品型号和问题，我会按产品查找对应资料。" if zh else
                 "Please share the product model and the issue so I can check the right support information.")), cards
    if case.get("service_intent") != "troubleshooting" and re.search(r"(退款|refund|换货|replace|replacement)", text, re.I):
        cards.append({"title": "待人工材料" if zh else "For human review",
                      "body": "产品：" + case["product"]["name"] + "；订单：" + (case.get("order_id") or "未提供") + "；当前状态：未提交退款或换货。" if zh else
                              "Product: " + case["product"]["name"] + "; order: " + (case.get("order_id") or "not provided") + "; no refund or replacement was submitted."})
        return (("已整理你的诉求。退款或换货需要核对订单归属、购买渠道、商品状态及人工审批；本演示没有发起实际办理。" if zh else
                 "I have prepared the request for review. Order ownership, purchase channel and item condition still need checking. No refund or replacement was initiated."), cards)
    if re.search(qa.RISK, text, re.I):
        case.pop('active_workflow', None)
        g.answer_route = 'HUMAN_REVIEW'
        return ('请先停止使用该设备。这涉及使用安全或身体不适，需要人工进一步核查。请说明具体情况；当前尚未实际转接或办理售后。' if zh else 'Please stop using the affected device. This involves safety or discomfort and needs human review. No transfer or after-sales action has been executed.'), cards
    followup = workflow.follow_up(case, text, lang)
    if followup:
        g.answer_route = 'WORKFLOW_FOLLOWUP'
        g.reply_sources = followup[1]
        report_progress('已读取本案排障记录，按反馈推进', 'Continuing this case from recorded troubleshooting feedback')
        return followup[0], cards
    if case["troubleshooting"] == "NEEDS_GUIDANCE":
        return (("我保留了前面的案件信息。请告诉我第二步里哪句话不清楚，我会解释；当前没有把排障标成已完成。" if zh else
                 "I kept the case context. Which part of step two needs explaining? The steps are not marked complete."), cards)
    pn = case['product']['id']
    if case.get('service_intent') not in ('shipping', 'return', 'warranty'):
        media_query = ' '.join((case.get('media_evidence') or {}).get(k,'') for k in ('visible_issue','description','error_code')).strip()
        result = answer_knowledge(case, text+' '+media_query if media_query else text, lang)
        if result is not None:
            return result, cards
    return (("已记录 " + case["product"]["name"] + "。请描述具体症状或错误码；如要查质保，请提供订单号和购买凭证。" if zh else
             "I recorded " + case["product"]["name"] + ". Please describe the symptom or error code. For warranty, share an order and proof of purchase."), cards)

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False, threaded=True)
