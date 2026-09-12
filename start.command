#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -e .
fi
echo 'Open http://127.0.0.1:8000 in your browser. Press Control-C to stop.'
exec .venv/bin/python -m organized_mom
