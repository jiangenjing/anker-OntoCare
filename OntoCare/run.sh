#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
if [ -f .env.local ]; then
  set -a
  source .env.local
  set +a
fi
export PORT="${PORT:-5088}"
echo "OntoCare → http://127.0.0.1:$PORT"
exec .venv/bin/python app.py
