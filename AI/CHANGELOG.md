# Changelog

## 1.0.5 — 2026-11-06
- Added `scripts/activate-worker-proxy.sh`: guided activation of Worker proxy mode (origin + optional Access service token), stores Worker secrets via Wrangler, deploys, and verifies `/api/health` through the proxy. Bash syntax checked; live Cloudflare activation requires owner credentials.

## 1.0.4 — 2026-11-06
- Added optional Cloudflare Worker reverse-proxy mode (`OMNIFIX_ORIGIN`) for an already-running OmniFix origin, while preserving the default static guard notice when unconfigured.
- Proxy mode forwards auth cookies/CSRF safely, rewrites upstream redirects/cookie domains, rejects foreign browser origins, supports optional Cloudflare Access service-token headers, and avoids caching private responses.
- Added `cloudflare-worker/README.md` with proxy/Access setup and warnings; updated README and Cloudflare build-error guide.
- Verified locally with Wrangler dev against the running OmniFix app: health, session, login, document list, upload, processing, original/processed download, delete cleanup, foreign-origin rejection, and scheme-relative path guard. Real Tunnel/Access proxy deployment still requires owner Cloudflare variables/secrets.

## 1.0.3 — 2026-11-06
- Added `scripts/restore.sh`: validates backup archive paths, rejects links, moves existing storage aside with `--force`, extracts database/private storage and runs SQLite integrity check.
- Verified a sandbox backup/restore drill: restored copy passed integrity, owner login, document listing and original-file serving.
- Documented restore helper in README and `docs/BACKUP_RESTORE.md`; ignored `backups/` and pre-restore directories.
- Replaced stale `next lint` with ESLint 9 flat config (`eslint-config-next`), added `npm run lint` to the test script, and overrode vulnerable transitive `minimatch` to keep `npm audit` at 0 vulnerabilities.

## 1.0.2 — 2026-11-06
- Added a Cloudflare Workers Builds guard (`wrangler.toml` + static notice Worker) so accidental `npx wrangler deploy` integrations deploy a clear notice instead of failing on missing static assets. The guard is not the OmniFix application; real deployment remains Docker + Cloudflare Tunnel.
- Verified guard with `wrangler deploy --dry-run` (Wrangler 4.158.0, Node 22).
- Added `scripts/deploy-cloudflare.sh` helper for Docker hosts: prompts for hostname/token, writes production `.env`, starts stack + cloudflared, waits for health and bootstraps owner. Bash syntax checked; Docker runtime not executed in sandbox.

## 1.0.1 — 2026-11-06
- Raised default upload limits: 50 MB per image, 100 MB per PDF, 500 MB per request, 300 pages per document/batch.
- Updated Nginx upload body limit to 500 MB and proxy timeouts to 600s; raised API container memory limit to 1 GB.
- Updated scan UI batch limit and format hint to 300 pages/files.
- Documented Cloudflare free/pro 100 MB request-body cap and recommended `MAX_UPLOAD_MB=90` / `MAX_PDF_MB=90` behind Tunnel.
- Added regression tests for total request size limit and batch page limit. Verified: 44 backend/engine tests, 7 frontend unit tests, TypeScript and production build.

## 1.0.0 — 2026-11-05
- Initialized monorepo from an empty workspace.
- Implemented FastAPI backend, SQLAlchemy/Alembic models, private storage, Argon2id auth, sessions/CSRF/rate limits, optional TOTP.
- Implemented deterministic OmniFix engine, conservative detection, safe perspective, adaptive enhancement, preservation checks.
- Implemented durable worker, jobs/history/cancel/retry, PDF import/export, ZIP exports.
- Implemented local OCR Smart Document Naming (de/en/ar) with editable suggestions.
- Implemented Next.js PWA: dashboard, scan, documents, workspace/corner editor/previews, history, export, settings, security, about; light/dark/system themes.
- Added Docker Compose/Nginx/Dockerfiles, setup/bootstrap/dev/start/test/backup scripts and documentation.
- Added backend/security/engine/visual/frontend/browser tests and synthetic dataset.
- Security remediation: upgraded Pillow 13.0.0, cryptography 50.0.0, python-multipart 0.0.33, pydantic-settings 2.16.2, pytest 9.0.3; Next 16.4.5, Vitest 4.1.12, PostCSS 8.5.32, Vite 7.3.7. Final pip-audit and npm audit report no known vulnerabilities.
- Verified: 42 backend/engine tests, 7 frontend unit tests, 2 browser E2E tests, TypeScript and production build.
- Documented unverified Docker/physical-device checks and known limitations.
