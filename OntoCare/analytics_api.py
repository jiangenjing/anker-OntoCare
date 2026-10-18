"""Read-only analytics and local review decisions; no external report delivery."""
import json
from pathlib import Path
from threading import Lock
from flask import Blueprint,jsonify,request,send_from_directory
import attribution as a
bp=Blueprint('analytics',__name__)
LOCK=Lock();REVIEWS=Path(__file__).parent/'local_state/faq_reviews.json'
@bp.get('/analytics')
def page():return send_from_directory('static','analytics.html')
@bp.get('/api/analytics')
def analytics():return jsonify(a.dashboard())
@bp.get('/api/analytics/report/<kind>')
def report(kind):
 try:return jsonify(a.report(kind))
 except ValueError:return jsonify(error='未知报告类型'),400
@bp.route('/api/analytics/gaps',methods=['GET','POST'])
def gaps():
 with LOCK:
  states=json.loads(REVIEWS.read_text()) if REVIEWS.exists() else {}
  rows=a.gaps()
  if request.method=='POST':
   body=request.get_json(silent=True) or {};ident=body.get('id');status=body.get('status')
   if ident not in {r['id'] for r in rows} or status not in ['approved','rejected']:return jsonify(error='审核参数无效'),400
   states[ident]=status;REVIEWS.parent.mkdir(exist_ok=True)
   tmp=REVIEWS.with_suffix('.tmp');tmp.write_text(json.dumps(states));tmp.replace(REVIEWS)
  return jsonify(rows=[dict(r,status=states.get(r['id'],r['status'])) for r in rows],note='审核通过仅确认待补课候选，不自动发布到正式知识库。')
