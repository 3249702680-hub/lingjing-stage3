#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$APP_DIR"
PYTHON="${PYTHON:-$APP_DIR/.venv/bin/python}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python not found: create .venv and install requirements.txt first." >&2
  exit 1
fi
if [[ ! -f "$APP_DIR/weights/garbage_detect.pt" ]]; then
  echo "Missing weights/garbage_detect.pt." >&2
  exit 1
fi
: "${DASHSCOPE_API_KEY:?Set DASHSCOPE_API_KEY in the process environment}"
: "${SQLSERVER_HOST:?Set a SQL Server host reachable from Linux}"
mkdir -p uploads

# One worker shares one CPU YOLO model. Use a service manager for restarts.
exec "$PYTHON" -m uvicorn app:app --host "$HOST" --port "$PORT" --workers 1
