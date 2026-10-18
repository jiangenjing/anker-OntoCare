"""OpenAI-compatible inference adapter. Credentials live in process memory only."""
import json
from contextlib import contextmanager
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

LOCK = threading.RLock()
REQUEST_SLOTS=threading.BoundedSemaphore(2)
RATE_LOCK=threading.Lock()
COOLDOWN={}
TURN = threading.local()

def start_turn(seconds=24):
    TURN.started = time.monotonic()
    TURN.deadline = TURN.started + seconds
    TURN.requests = []
    TURN.low_latency = seconds<=8

def remaining_time():
    return max(0, getattr(TURN, 'deadline', float('inf')) - time.monotonic())

def turn_metrics():
    return {'total_ms': round((time.monotonic() - TURN.started) * 1000),
            'outbound_requests': len(getattr(TURN, 'requests', [])),
            'requests': list(getattr(TURN, 'requests', []))} if hasattr(TURN, 'started') else {}

def end_turn():
    for key in ['started', 'deadline', 'requests', 'low_latency']:
        if hasattr(TURN, key): delattr(TURN, key)

@contextmanager
def provider_slot(base):
    """Share the same outbound limit across dialogue and capability-centre calls."""
    host=urllib.parse.urlparse(base).hostname
    acquired = REQUEST_SLOTS.acquire(timeout=min(.15 if getattr(TURN,"low_latency",False) else 24, remaining_time()))
    if not acquired:
        raise TimeoutError('turn queue deadline')
    try:
        with RATE_LOCK:pause=max(0,COOLDOWN.get(host,0)-time.monotonic())
        if pause:
            if pause >= remaining_time(): raise TimeoutError('turn rate limit deadline')
            time.sleep(min(pause,20))
        yield
    finally:
        REQUEST_SLOTS.release()

def rate_limited(base,headers=None):
    try:seconds=float((headers or {}).get('Retry-After',3))
    except (TypeError,ValueError):seconds=3
    host=urllib.parse.urlparse(base).hostname
    with RATE_LOCK:COOLDOWN[host]=max(COOLDOWN.get(host,0),time.monotonic()+max(2,min(seconds,20)))
CONFIG = {"base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
          "fallback_model": os.getenv("LLM_FALLBACK_MODEL", ""),
          "model": os.getenv("LLM_MODEL", "deepseek-flash"), "api_key": os.getenv("LLM_API_KEY", ""),
          "vision_base_url": os.getenv("VISION_BASE_URL", ""), "vision_model": os.getenv("VISION_MODEL", ""),
          "vision_api_key": os.getenv("VISION_API_KEY", ""), "protocol":os.getenv("LLM_PROTOCOL","openai"),
          "vision_protocol":os.getenv("VISION_PROTOCOL","openai"),
          "gateway_base_url":os.getenv("COMPETITION_BASE_URL","https://ai-router-cn-pub.anker-in.com"),
          "gateway_api_key":os.getenv("COMPETITION_API_KEY","")}

def validate_api_key(value):
    if any(not 33 <= ord(c) <= 126 for c in value):
        raise ValueError("Key 含有空格、换行、中文或不可见字符。请只复制密钥正文，不要包含标签或 Bearer 前缀。")
    if value.lower().startswith('bearer'):
        raise ValueError("请只填写密钥正文，不要包含 Bearer 前缀。")

def inference_options(base, name, max_tokens):
    options={'max_tokens':max_tokens}
    host=urllib.parse.urlparse(base).hostname
    if host=='api.deepseek.com' or (host=='ai-router-cn-pub.anker-in.com' and 'deepseek' in name):
        options.update(thinking={'type':'disabled'})
        if host!='api.deepseek.com':
            options['enable_thinking']=False
            options['max_tokens']=max(max_tokens,4096)
    if host=='ai-router-cn-pub.anker-in.com' and ('qwen' in name or 'kimi' in name):options['enable_thinking']=False
    return options

class OutputLimitError(ValueError):
    pass

class ResponseSchemaError(ValueError):
    pass

def rows_contract(root, expected_ids, row_kind):
    """Validate the response contract, not the truth of the proposed content."""
    def validate(proposal):
        values=proposal.get(root)
        if not isinstance(values,list):return 'Return an array under '+root
        id_key='id' if row_kind=='checks' else 'task_id'
        ids=[row.get(id_key) for row in values if isinstance(row,dict)]
        if len(ids)!=len(values) or len(ids)!=len(expected_ids) or set(ids)!=set(expected_ids):
            return 'Return exactly one row for each supplied '+id_key+': '+', '.join(expected_ids)
        for row in values:
            if row_kind=='selections' and (not isinstance(row.get('knowledge_ids'),list) or not all(isinstance(k,str) for k in row['knowledge_ids'])):
                return 'knowledge_ids must be an array of strings, including [] for NO_MATCH'
            if row_kind=='answers':
                if not isinstance(row.get('blocks'),list):return 'blocks must be an array, including [] when unsupported'
                if any(not isinstance(b,dict) or not all(isinstance(b.get(k),str) for k in ['text','knowledge_id']) or not any(isinstance(b.get(k),str) and b[k] for k in ['passage_id','source_quote']) for b in row['blocks']):
                    return 'Each block needs string text, knowledge_id and a provided passage_id'
                if row.get('followup') is not None and not isinstance(row['followup'],str):return 'followup must be a string or empty'
            if row_kind=='checks' and type(row.get('supported')) is not bool:return 'supported must be boolean'
        return None
    return validate

def public_config():
    with LOCK:
        return {k: v for k, v in CONFIG.items() if "key" not in k} | {
            "configured": bool(CONFIG["api_key"]), "vision_configured": bool(CONFIG["vision_api_key"] and CONFIG["vision_model"]),
            "key_storage": "PROCESS_MEMORY"}

def configure(values):
    with LOCK:
        updated = dict(CONFIG)
        for key in CONFIG:
            if key in values and isinstance(values[key], str):
                value = values[key].strip()
                if "base_url" in key and value:
                    u = urllib.parse.urlparse(value)
                    if u.scheme != "https" or not u.hostname or u.username or u.password:
                        raise ValueError("模型接口地址需要使用有效的 HTTPS 地址。")
                if len(value) > 1000:
                    raise ValueError("设置值过长。")
                if key.endswith('protocol') and value not in {'openai','anthropic'}:
                    raise ValueError('协议需要是 openai 或 anthropic。')
                if "key" in key and not value:
                    continue
                if "key" in key:
                    validate_api_key(value)
                updated[key] = value
        for prefix in ["", "vision_", "gateway_"]:
            old_host = urllib.parse.urlparse(CONFIG[prefix + "base_url"]).netloc
            new_host = urllib.parse.urlparse(updated[prefix + "base_url"]).netloc
            if new_host and old_host != new_host and CONFIG[prefix + "api_key"] and not values.get(prefix + "api_key", "").strip():
                raise ValueError("切换模型服务地址时，请填写该服务对应的密钥。")
        CONFIG.update(updated)
    return public_config()

def _call(messages, vision=False, max_tokens=1100, structured=True, validator=None, timeout_seconds=None, retries=2):
    call_started=time.monotonic()
    with LOCK:
        prefix = "vision_" if vision else ""
        base, name, key = CONFIG[prefix + "base_url"], CONFIG[prefix + "model"], CONFIG[prefix + "api_key"]
        protocol=CONFIG.get(prefix+'protocol','openai')
        fallback=CONFIG.get('fallback_model','') if not vision else ''
    if not (base and name and key):
        return None, {"status": "NOT_CONFIGURED", "label": "视觉未连接" if vision else "规则演示"}
    try:
        validate_api_key(key)
    except ValueError as error:
        return None, {"status":"ERROR", "label":"密钥格式需核对", "attempts":0,
                      "error_code":"INVALID_API_KEY", "retryable":False, "error":str(error)}
    options=inference_options(base,name,max_tokens)
    body = {"model": name, "messages": messages, "temperature": 0, **options}
    if not vision and structured:
        body["response_format"] = {"type": "json_object"}
    extra_headers={}
    path='/chat/completions'
    if protocol=='anthropic':
        from .resources import anthropic_messages
        system,converted=anthropic_messages(messages)
        body={'model':name,'system':system,'messages':converted,'max_tokens':options['max_tokens']}
        extra_headers={'x-api-key':key,'anthropic-version':'2023-06-01'}
        path='/v1/messages'
    req = urllib.request.Request(base.rstrip("/") + path,
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "OntoCare/3.0",**extra_headers})
    failure = None
    for attempt in range(retries):
        if remaining_time() < .5:
            return None, {'status':'ERROR', 'label':'本轮等待预算已用尽', 'attempts':attempt,
                          'error_code':'TURN_DEADLINE', 'retryable':True}
        started = time.monotonic()
        try:
            with provider_slot(base):
                timeout = min(timeout_seconds or 14, remaining_time())
                if timeout < .5: raise TimeoutError('turn deadline')
                if hasattr(TURN, 'requests'): TURN.requests.append({'model':body['model'],'attempt':attempt+1})
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw = json.load(response)
            choice = ({'message':{'content':'\n'.join(b.get('text','') for b in raw.get('content',[]) if isinstance(b,dict) and b.get('type')=='text')},'finish_reason':raw.get('stop_reason')} if protocol=='anthropic' else raw["choices"][0])
            if choice.get('finish_reason') in {'length','max_tokens'}:
                raise OutputLimitError()
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("invalid structured response")
            if not structured:
                if not content.strip():
                    raise ValueError("empty response")
                proposal = {"answer": content.strip()}
            else:
                start = content.find("{")
                proposal, _ = json.JSONDecoder().raw_decode(content[start:]) if start >= 0 else (None, 0)
            if not isinstance(proposal, dict):
                raise ValueError("invalid structured response")
            if validator:
                schema_error=validator(proposal)
                if schema_error:raise ResponseSchemaError(schema_error)
            return proposal, {"status": "OK", "label": body['model'], "model": body['model'], "attempts": attempt + 1,
                              "usage": raw.get("usage", {}), "role": "语言模型",
                              'duration_ms':round((time.monotonic()-call_started)*1000),
                              'fallback_used':bool(attempt and body['model']!=name),
                              "finish_reason": choice.get("finish_reason")}
        except urllib.error.HTTPError as err:
            if err.code==429:rate_limited(base,err.headers)
            retryable = err.code in {408, 429, 500, 502, 503, 504}
            failure = {"error_code": "PROVIDER_HTTP_" + str(err.code), "retryable": retryable,
                       "error": "模型接口返回 HTTP " + str(err.code)}
            if not retryable:
                break
        except OutputLimitError:
            failure={"error_code":"OUTPUT_LIMIT", "retryable":True,
                     "error":"模型输出达到长度上限，未使用不完整回答。"}
            if attempt==0:
                body['max_tokens']=min(8192,body['max_tokens']*2)
                req.data=json.dumps(body).encode()
        except ResponseSchemaError as error:
            failure={'error_code':'INVALID_RESPONSE_SCHEMA','retryable':True,
                     'error':'模型未按任务返回完整结构，未把缺失任务当作知识库无答案。'}
            if attempt==0:
                body['messages'].append({'role':'user','content':'Repair output format: '+str(error)+'. Return only the requested JSON. Keep all original source and authority constraints.'})
                req.data=json.dumps(body).encode()
        except (ValueError, KeyError, TypeError):
            failure = {"error_code": "INVALID_STRUCTURED_OUTPUT", "retryable": True,
                       "error": "模型返回的结构化内容不完整或无效。"}
        except Exception:
            failure = {"error_code": "TIMEOUT_OR_NETWORK", "retryable": True,
                       "error": "模型服务超时或网络连接未完成。"}
        if attempt == 0 and attempt+1<retries:
            if (fallback and protocol=='openai' and urllib.parse.urlparse(base).hostname=='ai-router-cn-pub.anker-in.com'
                    and failure and failure['error_code'] in {'TIMEOUT_OR_NETWORK','PROVIDER_HTTP_429','PROVIDER_HTTP_500','PROVIDER_HTTP_502','PROVIDER_HTTP_503','PROVIDER_HTTP_504'}):
                body['model']=fallback
                body.pop('thinking', None)
                body.update(inference_options(base, fallback, max_tokens))
                req.data=json.dumps(body).encode()
            time.sleep(.25)
    return None, {"status": "ERROR", "label": "模型调用失败", "attempts": attempt + 1,
                  'duration_ms':round((time.monotonic()-call_started)*1000), **failure}
