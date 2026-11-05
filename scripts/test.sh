#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONPATH=backend:. .venv/bin/python -m pytest backend/tests processing/tests -q
(cd frontend && npm run typecheck && npm test && npm run build)
echo "For browser tests: OWNER_PASSWORD=... npm run test:e2e --prefix frontend"
