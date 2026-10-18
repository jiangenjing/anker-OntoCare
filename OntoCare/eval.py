"""
Golden Case 回归评测 —— 测规则层不变量（不调 LLM）。
运行：python eval.py
覆盖赛题五难点：看图/问清/分流/接稳/幻觉，以及 L3 闭环动作约束。
"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ank", "app.py")
m = importlib.util.module_from_spec(spec); sys.modules["ank"] = m; spec.loader.exec_module(m)

def run(text, order_id=None, troubleshoot="NOT_STARTED"):
    od = m.lookup_order(order_id) if order_id else {"status":"NOT_FOUND","warranty":"UNKNOWN"}
    sku = od.get("order",{}).get("sku") if od["status"]=="FOUND" else None
    pr = m.resolve_product(text, sku)
    ds = m.match_dealer(od.get("order",{}).get("country"), od.get("order",{}).get("seller"))["status"] if od["status"]=="FOUND" else "UNKNOWN"
    case = {"product":pr["product"],"warranty":od["warranty"],"dealer":ds,
            "within_30d":od.get("within_30d",False),"troubleshooting":troubleshoot}
    fa,fb,_ = m.allowed_actions(case)
    return {"product":pr["product"]["id"] if pr["product"] else None,
            "warranty":od["warranty"],"dealer":ds,"allowed":fa,"forbidden":fb,
            "emotion":m.detect_emotion(text),"scope":m.detect_scope(text)}

CASES = [
 ("1 S1 Pro吸奶器消歧",        "My S1 Pro is not sucking", "ORD-2001", {"product":"BP-S1","warranty":"VALID"}),
 ("2 S1 Pro扫地机(订单定位)",   "robot won't charge",       "ORD-2002", {"product":"RV-S1","warranty":"VALID"}),
 ("3 订单查无→UNKNOWN",         "I want a replacement",     "ORD-9999", {"warranty":"UNKNOWN","forbidden":["propose_replacement","direct_refund"]}),
 ("4 在保授权",                 "robot won't charge",       "ORD-2005", {"warranty":"VALID"}),
 ("5 过保",                     "power bank is dead",       "ORD-2003", {"warranty":"EXPIRED","forbidden":["propose_replacement","direct_refund"]}),
 ("6 30天内授权→退款放行",       "refund this",              "ORD-2016", {"warranty":"VALID","allowed":["direct_refund"]}),
 ("7 超30天在保→退款拦",        "refund this",              "ORD-2005", {"warranty":"VALID","forbidden":["direct_refund"]}),
 ("8 非授权经销商→引导卖家",    "camera offline",           "ORD-2014", {"dealer":"NOT_AUTHORIZED","allowed":["guide_contact_seller"]}),
 ("9 愤怒情绪",                 "this is awful, send me a refund now!!!", None, {"emotion":"ANGRY"}),
 ("10 投诉风险情绪",            "I will complain to BBB",   None, {"emotion":"COMPLAINT_RISK"}),
 ("11 订单查无禁换货",          "replace it please",        "ORD-9999", {"forbidden":["propose_replacement"]}),
 ("12 排障失败+在保+授权→换货", "replace it please",       "ORD-2005", {"allowed":["propose_replacement"]}, "FAILED"),
 ("13 未知错误码不编造",        "",                         "ORD-2002", {"_fault":"unknown_error"}),
 ("14 服务边界→转人工",         "I want to speak to a manager", None, {"scope":"OUT_OF_SCOPE_HUMAN"}),
 ("15 超范围商务",              "I want bulk corporate order", None, {"scope":"OUT_OF_SCOPE_BUSINESS"}),
 ("16 正常咨询不越界",          "my robot won't charge",    None, {"scope":"IN_SCOPE"}),
 ("17 过保禁免费换货",          "replace it please",        "ORD-2003", {"forbidden":["propose_replacement"]}),
 ("18 德国经销商模糊匹配",      "robot vacuum problem",     "ORD-2002", {"dealer":"AUTHORIZED"}),
 ("19 产品未确定禁办理",        "it doesn't work",          "ORD-9999", {"forbidden":["propose_replacement","direct_refund"]}),
 ("20 非授权+在保禁换货",       "replace it please",        "ORD-2014", {"forbidden":["propose_replacement"],"dealer":"NOT_AUTHORIZED"}),
]

def check(actual, expect):
    fails=[]
    for k,v in expect.items():
        if k=="_fault":
            prod = actual["product"]
            kb = m.match_fault(prod, "e999 error") if prod else None
            if not (kb and kb.get("after_failed")=="honest_escalate_no_fabrication"):
                fails.append("未知错误码未路由到诚实升级")
            continue
        if k=="allowed":
            for a in v:
                if a not in actual["allowed"]: fails.append(f"allowed缺{a}")
        elif k=="forbidden":
            for a in v:
                if a not in actual["forbidden"]: fails.append(f"forbidden缺{a}")
        else:
            if actual.get(k)!=v: fails.append(f"{k}={actual.get(k)} != {v}")
    return fails

passed=0; rows=[]
for c in CASES:
    name,text,oid = c[0],c[1],c[2]; expect=c[3]; ts=c[4] if len(c)>4 else "NOT_STARTED"
    a=run(text,oid,ts)
    fails=check(a,expect)
    ok = not fails; passed+=ok
    rows.append((name, "PASS" if ok else "FAIL", "; ".join(fails) if fails else ""))

print(f"\n=== Golden Case 回归：{passed}/{len(CASES)} 通过 ===\n")
for name,st,msg in rows:
    print(f"  [{'✓' if st=='PASS' else '✗'}] {name:28} {msg}")
print(f"\n通过率：{passed/len(CASES)*100:.0f}%")
