"""Faults are scoped to one blue-team call, never to red-team or judge transport."""
import time,urllib.request,urllib.error
from contextlib import contextmanager
from unittest.mock import patch

@contextmanager
def inject(m,fault,counter):
 if not fault:yield;return
 def transport(*args,**kwargs):
  counter['fault_hits']+=1
  if fault=='timeout':time.sleep(.05);raise TimeoutError('injected timeout')
  if fault=='rate_limit':raise urllib.error.HTTPError('benchmark',429,'injected rate limit',{},None)
  class Partial:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self):return b'{"choices":['
  return Partial()
 if fault=='schema_drift':
  original=m.lookup_order
  def drift(*args,**kwargs):
   result=original(*args,**kwargs)
   if result.get('status')=='FOUND':
    counter['fault_hits']+=1;result['order']=dict(result['order']);result['order']['line_items']=result['order'].pop('items')
   return result
  with patch.object(m,'lookup_order',drift):yield
 else:
  with patch.object(m,'LLM_KEY',m.LLM_KEY or 'injected-no-network'),patch.object(m,'LLM_MODEL',m.LLM_MODEL or 'fault-probe'),patch.object(urllib.request,'urlopen',transport):yield
