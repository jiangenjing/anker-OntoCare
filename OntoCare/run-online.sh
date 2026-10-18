#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
export PORT="${PORT:-8000}"
echo "OntoCare 评委版 → http://127.0.0.1:$PORT"
exec .venv/bin/gunicorn judge_server:app --bind "0.0.0.0:$PORT" --workers 1 --threads 8 --timeout 120 --access-logfile -
