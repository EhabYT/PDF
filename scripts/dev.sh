#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && ../.venv/bin/alembic upgrade head)
(cd backend && ../.venv/bin/python -m app.workers.runner) &
WORKER_PID=$!
trap 'kill "$WORKER_PID" 2>/dev/null || true' EXIT
(cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload)
