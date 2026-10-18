"""Run in a child process: python benchmark/main.py --request request.json --output folder."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmark.orchestrator.runner import run,legacy
from benchmark.api import validate
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 try:
  legacy().load_env()
  run(validate(json.loads(Path(a.request).read_text())),a.output)
 except Exception as e:
  out=Path(a.output);out.mkdir(parents=True,exist_ok=True);(out/'error.json').write_text(json.dumps({'status':'FAILED','error_type':type(e).__name__}))
  raise SystemExit(1)
