"""Local demo API. Each run has an isolated subprocess and a unique output directory."""
import json,os,re,subprocess,sys,threading,uuid
from pathlib import Path
from urllib.parse import urlsplit
from flask import Blueprint,request,jsonify
from benchmark.orchestrator.runner import load_data,historical_trace
ROOT=Path(__file__).resolve().parents[1];OUTPUT=ROOT/'benchmark/output'
bp=Blueprint('benchmark',__name__);_jobs={};_lock=threading.Lock()

@bp.before_request
def local_only():
 if request.remote_addr not in ('127.0.0.1','::1'):return jsonify(error='评测控制接口仅支持本机访问'),403
 if request.headers.get('Origin') and urlsplit(request.headers['Origin']).netloc!=request.host:return jsonify(error='不允许跨站启动或读取评测'),403

def validate(body):
 if not isinstance(body,dict):raise ValueError('需要 JSON 对象')
 cases,_=load_data();valid={c['id'] for c in cases};ids=body.get('case_ids',['U093'])
 if not isinstance(ids,list) or not 1<=len(ids)<=110 or any(not isinstance(i,str) or i not in valid for i in ids) or len(ids)!=len(set(ids)):raise ValueError('case_ids 必须是源用例中的唯一编号')
 mode=body.get('mode','offline');red=body.get('red_mode','llm' if mode=='online' else 'scripted');turns=body.get('max_turns',3);repeats=body.get('repeats',1);judge=body.get('judge',mode=='online');fault=body.get('fault')
 if mode not in ('online','offline') or red not in ('llm','scripted') or type(turns) is not int or not 1<=turns<=8 or type(repeats) is not int or repeats not in (1,3,8) or type(judge) is not bool:raise ValueError('模式、轮数或重复次数无效')
 if fault not in (None,'timeout','rate_limit','partial_response','schema_drift'):raise ValueError('故障类型无效')
 if mode=='offline' and (red=='llm' or judge):raise ValueError('离线模式不能运行模型红队或模型裁判')
 if mode=='online' and not all(os.getenv(k) for k in ('LLM_API_KEY','LLM_MODEL','LLM_BASE_URL')):raise ValueError('尚未配置评测模型')
 return {'case_ids':ids,'mode':mode,'red_mode':red,'max_turns':turns,'repeats':repeats,'judge':judge,'fault':fault}

def folder(run_id):
 if not re.fullmatch(r'[a-f0-9]{32}',run_id or ''):return None
 path=OUTPUT/run_id;return path if path.is_dir() else None

@bp.post('/api/benchmark/run')
def start():
 try:config=validate(request.get_json(silent=True))
 except ValueError as e:return jsonify(error=str(e)),400
 with _lock:
  if any(p.poll() is None for p in _jobs.values()):return jsonify(error='已有评测运行中，请等待完成'),409
  run_id=uuid.uuid4().hex;out=OUTPUT/run_id;out.mkdir(parents=True);req=out/'request.json';req.write_text(json.dumps(config,ensure_ascii=False))
  with (out/'worker.log').open('wb') as log:
   proc=subprocess.Popen([sys.executable,str(ROOT/'benchmark/main.py'),'--request',str(req),'--output',str(out)],cwd=ROOT,stdout=log,stderr=log)
  _jobs[run_id]=proc
 return jsonify(run_id=run_id,status='RUNNING',status_url='/api/benchmark/runs/'+run_id),202

@bp.get('/api/benchmark/runs/<run_id>')
def status(run_id):
 out=folder(run_id)
 if not out:return jsonify(error='未找到评测'),404
 if (out/'error.json').exists():return jsonify(run_id=run_id,**json.loads((out/'error.json').read_text()))
 result=json.loads((out/'benchmark_results.json').read_text()) if (out/'benchmark_results.json').exists() else {}
 state='COMPLETED' if result.get('status')=='COMPLETED' else 'RUNNING'
 proc=_jobs.get(run_id)
 if state=='RUNNING' and (proc is None or proc.poll() is not None):state='INTERRUPTED'
 return jsonify(run_id=run_id,status=state,result=result)

@bp.get('/api/benchmark/trace/<case_id>')
def trace(case_id):
 cases,_=load_data();case=next((c for c in cases if c['id']==case_id),None)
 if case is None:return jsonify(error='用例不存在'),404
 run_id=request.args.get('run_id')
 if run_id:
  out=folder(run_id);repeat=request.args.get('repeat','1')
  if not out or repeat not in ('1','2','3','4','5','6','7','8'):return jsonify(error='运行编号或轮次无效'),404
  path=out/'traces'/f'{case_id}-{repeat}.json'
  if not path.exists():return jsonify(error='该轨迹尚未生成'),404
  return jsonify(json.loads(path.read_text()))
 mode=request.args.get('mode','online')
 if mode not in ('offline','online'):return jsonify(error='模式无效'),400
 for name in ('repair-final-results.json','benchmark-results.json'):
  path=ROOT/'benchmark'/name
  if not path.exists():continue
  row=next((r for r in json.loads(path.read_text())['results'] if r['id']==case_id and r['mode']==mode and r['repeat']==1),None)
  if row:
   obj=historical_trace(case,row);obj['result_source']=name;return jsonify(obj)
 return jsonify(error='没有该模式的记录'),404
