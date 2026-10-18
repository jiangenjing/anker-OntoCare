"""Read historical measurements without re-scoring or merging experiment versions."""
import hashlib
import json
from pathlib import Path


def build_history(root):
    root = Path(root)
    sources = []

    def load(path):
        blob = (root / path).read_bytes()
        data = json.loads(blob)
        timestamp = None
        if isinstance(data, dict):
            timestamp = data.get('generated_at') or data.get('run', {}).get('result', {}).get('created_at')
        sources.append({'path': path, 'sha256': hashlib.sha256(blob).hexdigest(),
                        'generated_at': timestamp})
        return data

    baseline = load('benchmark/benchmark-results.json')
    repair = load('benchmark/repair-final-results.json')
    metrics = load('benchmark/benchmark-metrics.json')['metrics']
    early = load('evaluation/results-live-reviewed.json')
    probe = load('benchmark/repair-fault-probe.json')
    labels = {
        'A003': '未核验地址披露', 'U012': '2310 错误码检索',
        'U013': '7031 错误码检索', 'U022': 'C10 / X10 产品切换',
        'U043': '西班牙语回复', 'U044': '拆单单号完整性',
        'U054': '接口字段异常兜底', 'U060': '超时注入未触发',
        'U062': '人工交接上下文',
    }
    examples = []
    for cid, label in labels.items():
        pair = {}
        for key, data in [('baseline', baseline), ('repair', repair)]:
            row = next(r for r in data['results'] if r['id'] == cid and
                       r['mode'] == 'online' and r['repeat'] == 1)
            pair[key] = row
        examples.append({'id': cid, 'label': label, **pair})

    redblue = []
    for filename in ['红蓝对抗在线实测-首次.json', '红蓝对抗在线实测-单轮.json',
                     '红蓝对抗在线实测.json']:
        item = load('reports/' + filename)
        run = item['run']['result']
        redblue.append({'source': 'reports/' + filename,
                        'run_id': item['run']['run_id'], 'created_at': run['created_at'],
                        'prompt_version': run['prompt_version'], 'summary': run['summary'],
                        'trace': item['trace']})

    return {
        'baseline': {'generated_at': baseline['generated_at'], 'config': baseline['config'],
                     'summary': baseline['summary']},
        'repair': {'generated_at': repair['generated_at'], 'config': repair['config'],
                   'summary': repair['summary']},
        'metrics': metrics, 'examples': examples, 'redblue': redblue,
        'early': {'counts': early['counts'], 'scope': early['scope'],
                  'total': len(early['results']),
                  'blocked': [r['id'] for r in early['results'] if r['status'] == 'BLOCKED']},
        'timeout_probe': {'id': probe['result']['id'], 'status': probe['result']['status'],
                          'checks': probe['result']['checks']},
        'sources': sources,
    }
