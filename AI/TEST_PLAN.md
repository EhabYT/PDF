# Test plan

## Automated (executed in sandbox)
- Backend/security/integration: `PYTHONPATH=backend:. .venv/bin/python -m pytest backend/tests processing/tests -q`.
- Engine visual dataset: synthetic normal/tilted/shadow/uneven/faint/stamp/signature/table + multipage PDF; original integrity, determinism, dimensions, faint/color preservation, baseline shape/mean/std.
- Frontend unit: `npm test` (Vitest + Testing Library).
- Type/build: `npm run typecheck && npm run build`.
- Browser E2E: `OWNER_PASSWORD=... npm run test:e2e` against a running instance; desktop Chromium + mobile Chromium; login/upload/process/compare/name/export/download/overflow.
- Dependency audits: `pip-audit -r backend/requirements.lock`, `npm audit`.

## Manual / external (pending)
- Docker Compose build/up/health/bootstrap on a Docker host.
- Nginx proxy/upload limits/TLS termination.
- Physical iPhone Safari and Android Chrome camera/upload/corner touch.
- Desktop Safari, Edge, Firefox.
- VPN/LAN access and firewall validation.
- Backup/restore drill on a copy of storage.

## Notes
Repeated E2E runs against the same instance can hit the real login rate limit. Use a fresh test instance or reset local test counters between runs; do not weaken production limits. Browser traces may contain test credentials — delete `frontend/test-results` after local runs.
