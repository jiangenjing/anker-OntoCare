"""Load the owner's preconfigured judging connection on every server start."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_BASE = 'https://ai-router-cn-pub.anker-in.com'
DEFAULT_TEXT_MODEL = 'hackathon/v_model/nova-pro'
DEFAULT_VISION_MODEL = 'hackathon/v_model/deepseek-v4.1-flash'


def load(path=None, environ=None):
    env = os.environ if environ is None else environ
    filename = Path(path or env.get('ONTOCARE_API_CONFIG') or
                    Path(__file__).with_name('demo_api_config.json'))
    data = {}
    if filename.exists():
        try:
            data = json.loads(filename.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise ValueError('无法读取 demo_api_config.json，请检查后端连接配置格式。') from None
        if not isinstance(data, dict):
            raise ValueError('后端连接配置必须为 JSON 对象。')
    for field in ('api_key', 'base_url', 'text_model', 'vision_model'):
        if field in data and not isinstance(data[field], str):
            raise ValueError('后端连接配置字段类型不正确：' + field)
    key = data.get('api_key', '')
    if key and (any(not 33 <= ord(char) <= 126 for char in key) or key.lower().startswith('bearer')):
        raise ValueError('后端 API Key 格式不正确，请仅填写密钥正文。')
    base = data.get('base_url') or env.get('LLM_BASE_URL') or DEFAULT_BASE
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('后端接口地址需为有效的 HTTPS 地址。')
    return {
        'LLM_BASE': base.rstrip('/'),
        'LLM_KEY': key or env.get('LLM_API_KEY') or env.get('COMPETITION_API_KEY', ''),
        'LLM_MODEL': data.get('text_model') or env.get('LLM_MODEL') or DEFAULT_TEXT_MODEL,
        'VLM_BASE': base.rstrip('/') if key else env.get('VISION_BASE_URL', base).rstrip('/'),
        'VLM_KEY': key or env.get('VISION_API_KEY') or env.get('COMPETITION_API_KEY', ''),
        'VLM_MODEL': data.get('vision_model') or env.get('VISION_MODEL') or DEFAULT_VISION_MODEL,
        'FIXED_CONNECTION': bool(key),
    }
