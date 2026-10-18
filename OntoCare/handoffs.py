"""Local review queue. Records requests; does not send email or connect an operator."""
import json
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent / 'data' / 'handoffs'


def create(session_id, case, channel):
    ROOT.mkdir(exist_ok=True)
    ident = uuid.uuid4().hex
    transcript = case.get('transcript', [])
    message = '\n\n'.join(('客户：' if t['role'] == 'user' else '助手：') + t['text'] for t in transcript)
    user_messages = [t['text'] for t in transcript if t['role'] == 'user']
    substantive = next((t for t in reversed(user_messages) if not re.fullmatch(r'下一步|继续|好了|还是不行|全部都试过了还是不行|第.步没看懂|next(?: step)?',t.strip(),re.I)), case.get('last_message',''))
    routing_message = substantive
    if substantive != case.get('last_message'):
        routing_message += '\n客户最新补充：' + case.get('last_message','')
    record = {'id': ident, 'channel': channel, 'status': 'WAITING_REVIEW',
              'created_at': datetime.now(timezone.utc).isoformat(), 'session_id': session_id,
              'emotion':case.get('emotion','NORMAL'), 'recommended_next_action':case.get('recommended_next_action') or 'Review the conversation and verify the purchase before approving service.',
              'customer_id': None, 'sku': case.get('selected_sku'),
              'product': case.get('product', {}).get('name') if case.get('product') else None,
              'order_id': case.get('order_id'), 'message': message,
              'latest_message':case.get('last_message',''), 'routing_message':routing_message, 'turn_count':case.get('turn_count',0)}
    (ROOT / (ident + '.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
    return record


def get(ident):
    if not isinstance(ident,str) or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
        return None
    path = ROOT / (ident + '.json')
    return json.loads(path.read_text()) if path.exists() else None


def all_records():
    return [json.loads(p.read_text()) for p in sorted(ROOT.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)]
