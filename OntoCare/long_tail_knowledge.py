"""Retrieve curated service strategies, never treat them as verified policy facts."""
from pathlib import Path
import re
import json

PATH = Path(__file__).parent / 'docs/knowledge/long_tail/长尾场景策略库.md'
DATA_DIR = Path(__file__).parent / 'knowledge/long_tail'
ENTRIES = {}
strategy_text = PATH.read_text() + '\n' + (PATH.parent / '评测修复策略库.md').read_text()
for block in re.split(r'^## ', strategy_text, flags=re.M)[1:]:
    head, _, body = block.partition('\n')
    if not head.startswith('long-tail-'):
        continue
    ident, title = head.split(' | ',1)
    def field(name):
        return re.search(r'^'+name+r'：(.*)$',body,re.M).group(1).strip()
    ENTRIES[ident] = {'id':ident,'title':title,'category':field('类别'),
                      'keywords':field('匹配词').split('|'),'slots':field('本体槽位'),
                      'strategy':field('处理策略'),'content':head+'\n'+body.strip()}
    if '固定回复中文：' in body:
        ENTRIES[ident]['direct_answers']={'zh':field('固定回复中文').replace('\\n','\n'),'en':field('固定回复英文').replace('\\n','\n')}
        ENTRIES[ident]['condition']=field('适用条件')


for item in (json.loads((DATA_DIR / '长尾问题_检索策略.json').read_text()) + json.loads((DATA_DIR / '双语补充_检索策略.json').read_text()) + json.loads((DATA_DIR / '多模态_检索策略.json').read_text())):
    ENTRIES[item['id']] = item


def product_guide(item):
    return item.get('product_specific', item['id'] in {'long-tail-eval-002','long-tail-eval-004'} or item['id'] in {'long-tail-'+str(n).zfill(3) for n in (25,39,40,41,42,43,44,45,46)})


def retrieve(text, limit=3, pn=None):
    explicit = re.findall(r'(?i)T[A-Z0-9]{4}', text)
    active_pns = {p.upper() for p in explicit} or ({pn.upper()} if pn else set())
    text=re.sub(r'\s+','',text).casefold()
    scored=[]
    for item in ENTRIES.values():
        if item.get('pn') and not active_pns.intersection(item['pn'].upper().split(';')):
            continue
        matches=[k for k in item['keywords'] if re.sub(r'\s+','',k).casefold() in text]
        if matches:
            scored.append((max(map(len,matches)),item))
    return [item for _,item in sorted(scored,key=lambda p:-p[0])[:limit]]


def citation(item):
    return {'id':item['id'],'kind':'strategy','label':f"长尾核查策略 · {item['id']} · {item['title']}（非官方政策）",'url':'/api/sources/'+item['id']}


def fallback(items, lang):
    if lang=='en':
        return ('I understand this needs a more specific review.\n\nThe matched supplementary notes are review strategies, not verified product policies or live order facts. I cannot confirm eligibility, fees or timing from them.\n\nPlease confirm the purchase channel so the applicable policy can be checked. No business action has been executed.')
    return '我理解，这个情况需要进一步核对。\n\n'+items[0]['strategy']+'\n\n以上是核查建议，不代表已办理，也不是已确认的官方政策。可以先补充当前缺少的关键信息，再确定处理路径。'


def direct_answer(items, case, language):
    for item in items:
        if item.get('condition') == 'privacy_request' and language in item.get('direct_answers', {}):
            return {'reply': item['direct_answers'][language], 'source': citation(item)}
    return None
