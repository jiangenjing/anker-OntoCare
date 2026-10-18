"""Adapter to the real app, not a separate chatbot. Used only inside a worker process."""
import json,time
from unittest.mock import patch
from benchmark.config.prompts import BLUE_TEAM_SYSTEM_PROMPT

def send(app_module,session_id,text):
 m=app_module;start=time.monotonic();events=[];first=None;answer={};status=500
 with patch.object(m,'RESPONSE_GUIDE',m.RESPONSE_GUIDE+'\n'+BLUE_TEAM_SYSTEM_PROMPT),patch.object(m.grounded_response,'PROMPT',m.grounded_response.PROMPT+'\n'+BLUE_TEAM_SYSTEM_PROMPT):
  with m.app.test_client() as client:
   response=client.post('/api/chat/stream',json={'session_id':session_id,'message':text,'language':'auto'},buffered=False)
   for chunk in response.response:
    for line in chunk.decode().splitlines():
     event=json.loads(line);events.append(event)
     if event.get('type')=='progress' and first is None:first=round((time.monotonic()-start)*1000,2)
     if event.get('type')=='result':answer=event['data'];status=event['status']
   response.close()
 state=m.SESSIONS.get(session_id,{})
 snapshot={'order_id':state.get('order_id'),'selected_sku':state.get('selected_sku'),'product_id':(state.get('product') or {}).get('id'),'warranty':state.get('warranty'),'dealer':state.get('dealer'),'troubleshooting':state.get('troubleshooting'),'turn_count':state.get('turn_count',0),'response_language':state.get('response_language')}
 elapsed=round((time.monotonic()-start)*1000,2)
 return {'input':text,'status':status,'response':answer,'events':events,'state':snapshot,'latency_ms':elapsed,'answer_ttft_ms':elapsed,'first_progress_ms':first}
