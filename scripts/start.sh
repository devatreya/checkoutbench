#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo 'Run uv sync --python 3.12 --extra test --extra agent first.' >&2
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  npm --prefix frontend ci
  npm --prefix frontend run build
fi
exec .venv/bin/python -m backend.main
