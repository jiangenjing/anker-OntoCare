"""Evaluation-only model transport. Does not use the Flask request globals."""
import json,os,time,urllib.request

def complete(system,payload):
 start=time.monotonic()
 if not os.getenv('LLM_API_KEY') or not os.getenv('LLM_MODEL'):
  return None,{'status':'NOT_CONFIGURED','calls':0}
 try:
  model=os.environ['LLM_MODEL']
  body={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],'temperature':0,'max_tokens':1800,'response_format':{'type':'json_object'}}
  if 'deepseek' in model.lower():body['thinking']={'type':'disabled'}
  req=urllib.request.Request(os.environ['LLM_BASE_URL'].rstrip('/')+'/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+os.environ['LLM_API_KEY'],'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=45) as res:data=json.loads(res.read())
  obj=json.loads(data['choices'][0]['message']['content'])
  if not isinstance(obj,dict):raise ValueError('object required')
  return obj,{'status':'OK','calls':1,'model':model,'duration_ms':round((time.monotonic()-start)*1000)}
 except Exception as e:
  return None,{'status':'ERROR','calls':1,'error_type':type(e).__name__,'duration_ms':round((time.monotonic()-start)*1000)}
