#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/preflight.sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
(cd frontend && npm ci --no-audit --no-fund)
if [ ! -f .env ]; then
  cp .env.example .env
  SECRET=$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')
  .venv/bin/python - "$SECRET" <<'PY'
import sys
from pathlib import Path
p=Path('.env'); s=p.read_text().replace('SESSION_SECRET=', 'SESSION_SECRET=' + sys.argv[1], 1); p.write_text(s)
PY
  chmod 600 .env
fi
(cd backend && ../.venv/bin/alembic upgrade head)
echo "Setup complete. Create the owner with: bash scripts/bootstrap.sh"
