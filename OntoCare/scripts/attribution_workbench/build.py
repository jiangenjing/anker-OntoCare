"""Build a standalone workbench from the evaluation suite and normalized long-tail library only."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / 'evaluation/ontocare-test-suite.json'
LIBRARY = ROOT / 'knowledge/long_tail/长尾问题_检索策略.json'

def build_data():
    suite = json.loads(SUITE.read_text())
    library = json.loads(LIBRARY.read_text())
    merchant = {c['id']: c for c in suite['merchant_test_cases']}
    scenarios = merchant['M009']['expected_aggregation']['buckets']
    codes = merchant['M008']['expected_aggregation']['buckets']
    rows = merchant['M007']['expected_aggregation']['buckets'][0]['rows']
    tickets = {r: dict(row=r, product=None, email=None, sources=[], codes=[], scenario=None, decision=None) for r in rows}
    for bucket in scenarios:
        for row in bucket['rows']:
            tickets[row]['scenario'] = bucket['label']
    for bucket in codes:
        if bucket['label'] != '未提供':
            for row in bucket['rows']:
                tickets[row]['codes'].append(bucket['label'])
    def add(row, email, source):
        if row not in tickets or not email:
            return
        t = tickets[row]
        t['email'] = email
        t['sources'].append(source)
        # Extract only explicitly named product fields, never guess an SKU from prose.
        match = re.search(r'^(?:Product Name|Productnaam|Produktname|Nom du produit)\s*:\s*(.+)$', email, re.M | re.I)
        if match:
            t['product'] = match.group(1).strip()
    for c in suite['user_test_cases']:
        if c.get('fixture_type') in ('verbatim_source_email', 'verbatim_longest_source_email'):
            for ref in c['ground_truth_refs']:
                if ref['sheet'] == '客诉工单信息':
                    add(ref['excel_row'], c['input'], c['id'])
    for c in suite['merchant_test_cases']:
        if c.get('input_ticket_row') and not c.get('input_transform'):
            add(c['input_ticket_row'], c['input_email'], c['id'])
            if c['category'] == 'action_eligibility':
                tickets[c['input_ticket_row']]['decision'] = dict(source=c['id'], state=c['expected_case_state'], allowed=c['expected_allowed_actions'], blocked=c['expected_blocked_actions'], as_of=c['as_of_date'])
    product_groups = {}
    for t in tickets.values():
        if t['product']:
            product_groups.setdefault(t['product'], []).append(t['row'])
    products = [dict(label=k, count=len(v), rows=v) for k,v in product_groups.items()]
    products.sort(key=lambda b: (-b['count'], b['label']))
    fault_rows = sorted(t['row'] for t in tickets.values() if t['codes'])
    rules = [
        dict(id='DO-RC1', rc='RC1', title='上下文丢失', definition='核查跨轮、跨渠道交接是否丢失已提供的信息。', rows=[], source=['M004'], explanation='测评集 M004 明确：维修后地图丢失不等于客服对话上下文丢失。当前没有支持该归因的正例。', missing='完整对话记录、交接摘要、重复索取证据', action='补齐会话及交接记录后复核', strategy=None),
        dict(id='DO-RC2', rc='RC2', title='规则散落', definition='核查同一条件下的政策或客服指引是否存在冲突。', rows=[], source=['M005'], explanation='测评集 M005 明确：同一设备出现两种故障不能证明政策冲突。当前没有支持该归因的正例。', missing='冲突规则原文、版本、适用国家及渠道', action='对齐适用条件并核对政策版本', strategy='B018'),
        dict(id='DO-RC3', rc='RC3', title='产品设计', definition='将明确错误码工单列入产品设计方向的核查候选；需要进一步排除使用、维护和个体故障因素。', rows=fault_rows, source=['M008','M010','M011','M012'], explanation='按 M008 的非空错误码分组去重得到候选工单。错误码不是设计缺陷证据，候选数不是故障率。', missing='复现结果、使用条件、批次及工程分析', action='先按型号匹配知识，再收集复现证据提交工程复核', strategy=None),
        dict(id='DO-RC4', rc='RC4', title='过保临界点', definition='核对投诉发生日期与对应 SKU 的质保截止日期，确认是否处于业务定义的临界窗口。', rows=[], source=['M006','M015','M016','M017','M020'], explanation='M006 不支持过保临界归因。M015–M017 为指定日期的测评状态，不能代替真实投诉日期；过保也不等于临界。', missing='投诉日期、对应 SKU、质保截止日期、经审核的临界窗口', action='日期及渠道未核验前，只准备人工复核材料', strategy='B018')
    ]
    top = scenarios[0]
    findings = [
        dict(id='I01', title='排障与使用问题占主要工作量', description=f"{top['label']} 共 {top['count']} 条，占全量 {len(rows)} 条的 {top['count']/len(rows):.1%}。优先抽查这些工单的型号确认和已尝试步骤。", rows=top['rows'], action='按产品收集复现步骤；复核是否已有对应知识，避免重复询问客户。', rule='DO-RC3', source=['M009','M013'], strategies=[], missing='部分邮件正文和产品名称未收录在测评集'),
        dict(id='I02', title='明确错误码仍需验证原因与知识覆盖', description=f"{len(fault_rows)} 条工单含明确错误码；3212 出现 2 次。高频仅代表当前样本中的出现次数。", rows=fault_rows, action='先核对 3212、2111、2310 的适用型号与知识 ID；知识缺口提交人工补充，再决定是否升级工程核查。', rule='DO-RC3', source=['M008','M010','M011','M012','M014'], strategies=[], missing='知识缺口不能用其他型号的排障内容填补'),
        dict(id='I03', title='物流问题需要逐件核对包裹', description=f"Shipping inquiry 共 {next(b['count'] for b in scenarios if b['label']=='Shipping inquiry')} 条。将拆单、签收记录与实际收到的商品分开核查。", rows=next(b['rows'] for b in scenarios if b['label']=='Shipping inquiry'), action='按 SKU 核对全部物流单号，区分标签创建、签收快照与客户反馈；退款换货保留人工审核。', rule='DO-ACTION', source=['M009','U004','U005','U007','M015','M016','M017'], strategies=['L001','L002','L007','L008'], missing='测评集不是实时物流系统，不能承诺当前送达时间')
    ]
    rules.append(dict(id='DO-ACTION', rc=None, title='动作授权复核', definition='状态和归因只用于准备复核材料，不能直接执行退款或换货。', rows=[47,52,49], source=['M015','M016','M017'], explanation='测评期望允许 prepare_email_draft，阻止 direct_refund 和 propose_replacement。在保状态不能替代渠道和排障核验。', missing='渠道、归属、排障结果及执行权限', action='准备草稿并交人工审核', strategy='B018'))
    return dict(total=len(rows), reference_date=suite['metadata']['reference_date'], tickets=list(tickets.values()), scenarios=scenarios, products=products[:10], product_coverage=sum(b['count'] for b in products), product_groups=len(products), email_coverage=sum(bool(t['email']) for t in tickets.values()), rules=rules, findings=findings, knowledge_checks=[{k:merchant[i].get(k) for k in ['id','input_ticket_row','target_code','expected_knowledge_ids','knowledge_gap_expected']} for i in ['M010','M011','M012']], strategies=[{k:x.get(k) for k in ['id','source_entry','title','category','strategy','evidence_level']} for x in library], sources=[dict(file=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [SUITE,LIBRARY]])

def render():
    data = build_data()
    template = Path(__file__).with_name('template.html').read_text()
    html = template.replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('<','\\u003c'))
    target = ROOT.parent / 'OntoCare-归因工作台/index.html'
    target.parent.mkdir(exist_ok=True)
    target.write_text(html)
    (ROOT / 'static/analytics.html').write_text(html)
    print(json.dumps(dict(file=str(target),tickets=data['total'],named_products=data['product_coverage'],emails=data['email_coverage']),ensure_ascii=False))

if __name__ == '__main__':
    render()
