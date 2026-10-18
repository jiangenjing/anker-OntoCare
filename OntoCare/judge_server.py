"""Public presentation adapter. The existing chatbot and business rules are reused."""
import os
from flask import jsonify, request
from app import app

app.config['JUDGE_PUBLIC_DEMO'] = True
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024


@app.before_request
def judging_boundary():
    # Benchmark and local maintenance controls do not belong in the judging UI.
    body = request.get_json(silent=True) if request.is_json else None
    configuring = isinstance(body, dict) and bool(body.get('action'))
    if request.path.startswith('/api/benchmark') or request.path.startswith('/api/models') and request.method == 'POST' and configuring:
        return jsonify(error='此入口不属于评委体验功能。'), 404
    origin = request.headers.get('Origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
        from urllib.parse import urlsplit
        if urlsplit(origin).netloc != request.host:
            return jsonify(error='请从当前体验页面提交请求。'), 403


@app.get('/api/judge-health')
def judge_health():
    from ontocare_multimodal import model
    config = model.public_config()
    return jsonify(status='ready' if config['configured'] else 'needs_configuration',
                   edition='judges', configured=config['configured'],
                   text_model=config['model'], vision_model=config['vision_model']), (200 if config['configured'] else 503)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5100')), debug=False, threaded=True)
