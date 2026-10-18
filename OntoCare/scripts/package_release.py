"""Create a clean, reproducible release including the owner-authorized judging connection."""
from pathlib import Path
import json,shutil,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'OntoCare-评委演示精简版'/'OntoCare'
ZIP=ROOT.parent/'OntoCare-评委演示精简版.zip'

moves=json.loads((ROOT/'docs/architecture/reorganization-map.json').read_text())

def collect():
    files=set()
    def add(pattern):
        files.update(p for p in ROOT.glob(pattern) if p.is_file() and '__pycache__' not in p.parts)
    for pattern in ['*.py','demo_api_config.json','ontocare_multimodal/*.py','run.sh','requirements.txt','Procfile','docs/deployment/railway.md','.env.example','.gitignore','README.md','docs/architecture/system-overview.md','docs/**/*.md','static/**/*','tests/*','knowledge/long_tail/*','scripts/*.py','scripts/merchant_attribution/*','benchmark/agents/*.py','benchmark/orchestrator/*.py','benchmark/config/*.py']:
        add(pattern)
    files={p for p in files if p.name not in {'eval.py','eval_safe.py','用户提供原文_未核验_不参与检索.md','长尾问题_原始输入_不参与检索.json'} and '__pycache__' not in p.parts}
    for name in ['source.json','qa-workbooks.json','faq-cache.json','policies.json','mail-tickets.json','ontology-import-audit.json']:
        files.add(ROOT/'data'/name)
    for name in ['source-snapshot.json','ontocare-test-suite.json','results-live-reviewed.json']:
        files.add(ROOT/'evaluation'/name)
    for name in ['evaluation_history.py','results-view.html','results-view.js','README.md','ontocare-benchmark-runner.py','build_benchmark.py','compute_metrics.py','render_report.py','test_benchmark.py','report-template.html','trace-graph.html','ontocare-user-test-cases.json','ontocare-adversarial-tests.json','ontocare-persona-vectors.json','benchmark-results.json','benchmark-metrics.json','evaluator-audit-before.json','任务：为 OntoCare 安克智能客服 Agent 构建完整 Benchmark 评测体系.md','repair-final-results.json','repair_fault_probe.py','repair-fault-probe.json','__init__.py','main.py','api.py','INTEGRATION.md']:
        files.add(ROOT/moves.get('benchmark/'+name,'benchmark/'+name))
    for name in ['attribution_report.json','weekly_report.md','本次语言实测.json','本次交付验证（2026-10-17）.md','评测结果展示验收.md','评测失败复盘.json','评测失败修复说明.md','评测修复复测.json','红蓝对抗在线实测.json','红蓝对抗在线实测-首次.json','红蓝对抗在线实测-单轮.json','红蓝对抗集成验证.md','红蓝对抗集成验证.json']:
        files.add(ROOT/moves.get('reports/'+name,'reports/'+name))
    return sorted(files)

def build():
    files=collect()
    # Include only the owner-authorized demo connection; exclude other machine credentials, sessions and uploads.
    secret_values=[]
    local=ROOT/'.env.local'
    if local.exists():
        for line in local.read_text().splitlines():
            if '=' in line:
                key,value=line.split('=',1)
                if 'KEY' in key and len(value.strip().strip('\"\''))>12:secret_values.append(value.strip().strip('\"\''))
    for p in files:
        blob=p.read_bytes()
        if p != ROOT/'demo_api_config.json' and any(x.encode() in blob for x in secret_values):raise RuntimeError('Secret found in selected file: '+str(p.relative_to(ROOT)))
    if DEST.exists():
        if not (DEST/'release-manifest.json').exists():raise RuntimeError('Unrecognized existing destination')
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    for p in files:
        target=DEST/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    # Both served HTML pages are canonical; no duplicated generated HTML in benchmark/.
    manifest={'format_version':1,'files':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files], 'demo_connection':'demo_api_config.json included for ready-to-run judging by owner request', 'excluded':'virtualenv, other machine credentials, sessions, uploads, screenshots, logs, obsolete reports, duplicate dataset exports, legacy workbench builder'}
    (DEST/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    def tree(folder,prefix=''):
        entries=sorted(folder.iterdir(),key=lambda p:(p.is_file(),p.name))
        result=[]
        for i,p in enumerate(entries):
            last=i==len(entries)-1;result.append(prefix+('└── ' if last else '├── ')+p.name+('/' if p.is_dir() else ''))
            if p.is_dir():result.extend(tree(p,prefix+('    ' if last else '│   ')))
        return result
    (DEST/'docs/architecture/release-tree.md').write_text('# 精简交付包实际目录\n\n```text\nOntoCare/\n'+'\n'.join(tree(DEST))+'\n```\n\n源码目录树.md 为本目录清单；运行产生的缓存、会话和 .venv 不属于交付源码。\n')
    with zipfile.ZipFile(ZIP,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(DEST.rglob('*')):
            if p.is_file():z.write(p,Path('OntoCare')/p.relative_to(DEST))
    print(json.dumps({'zip':str(ZIP),'files':len(files)+2,'zip_bytes':ZIP.stat().st_size},ensure_ascii=False))
if __name__=='__main__':build()
