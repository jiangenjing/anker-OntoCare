"""Local demonstration routes; no credentials are returned to the browser."""
from urllib.parse import urlparse
from flask import request, jsonify
from ontocare_multimodal import model, resources


def register_model_demo(app, runtime):
    # Main conversation and the capability workbench share the same provider.
    with model.LOCK:
        model.CONFIG.update(base_url=runtime['LLM_BASE'], model=runtime['LLM_MODEL'],
                            api_key=runtime['LLM_KEY'], vision_base_url=runtime['VLM_BASE'],
                            vision_model=runtime['VLM_MODEL'], vision_api_key=runtime['VLM_KEY'],
                            gateway_base_url=runtime['LLM_BASE'], gateway_api_key=runtime['LLM_KEY'])

    def local_request():
        host = urlparse('http://' + request.host).hostname
        origin = request.headers.get('Origin')
        if app.config.get('JUDGE_PUBLIC_DEMO') and runtime.get('LLM_KEY') and runtime.get('VLM_KEY'):
            return not origin or urlparse(origin).netloc == request.host
        return (request.remote_addr in {'127.0.0.1', '::1'} and host in {'localhost', '127.0.0.1', '::1'}
                and (not origin or urlparse(origin).netloc == request.host))

    @app.route('/api/models', methods=['GET', 'POST'])
    def models():
        if not local_request():
            return jsonify(error='模型配置与测试仅允许在本机访问。'), 403
        if request.method == 'GET':
            catalog, config = resources.catalog(), model.public_config()
            if runtime.get('FIXED_CONNECTION'):
                catalog['key_storage'] = config['key_storage'] = 'SERVER_FILE'
                config['connection_locked'] = True
            return jsonify(catalog=catalog, config=config)
        if request.content_length and request.content_length > 32 * 1024 * 1024:
            return jsonify(error='文件超过演示上限。'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error='请求必须为 JSON 对象。'), 400
        try:
            if body.get('action') == 'configure':
                if runtime.get('FIXED_CONNECTION'):
                    return jsonify(error='演示连接已由后台预置，无需在页面配置。'), 403
                key = body.get('api_key', '')
                model.validate_api_key(key)
                if not key:
                    raise ValueError('请填写比赛 API Key。')
                model.configure({'gateway_base_url': resources.BASE, 'gateway_api_key': key,
                                 'base_url': resources.BASE, 'api_key': key,
                                 'vision_base_url': resources.BASE, 'vision_api_key': key})
                resources.activate('nova')
                resources.activate('deepseek-flash', vision=True)
                with model.LOCK:
                    for target, source in [('LLM_BASE','base_url'),('LLM_KEY','api_key'),('LLM_MODEL','model'),
                                           ('VLM_BASE','vision_base_url'),('VLM_KEY','vision_api_key'),('VLM_MODEL','vision_model')]:
                        runtime[target] = model.CONFIG[source]
                return jsonify(config=model.public_config(), message='已应用到客服问答和照片分析；尚未验证实际调用。')
            return jsonify(resources.run(body))
        except (ValueError, TypeError) as error:
            return jsonify(error=str(error)), 400
