# Changelog

## 1.0.10 — 2026-11-08
- Fixed the last remaining cause of "Security token missing or invalid": some embedded hosts (sandboxed cross-site preview iframes with an **opaque origin**) refuse to store cookies **at all**, so no `SameSite` setting could ever deliver the session cookie and every upload/save failed. Symptom: a new session row on nearly every request (66 accumulated).
- Added `COOKIE_FALLBACK_HEADER` (default `false`): an opt-in, **no-login-mode-only** transport where `GET /api/auth/session` returns the opaque session token and the SPA echoes it in `X-Session-Token`. The CSRF token is still required on every mutation, so no new secret is exposed beyond what the browser already holds, and cookie storage is never weakened.
- Middleware and `current_session` now share one `session_token()` resolver so the CSRF check and dependency can never disagree. CORS allows `X-Session-Token`. Download URLs send it too.
- Ignored entirely when `AUTH_DISABLED=false`; the token is never returned in normal login deployments. Service worker cache bumped to `v3`.
- Tests: backend+engine **51 passed**, including `test_header_session_transport_opt_in`, `test_header_transport_disabled_by_default`, `test_header_transport_requires_no_login_mode`. Verified live with a browser storing **zero cookies**: session 200, upload **202**, settings PATCH 200, delete 200, 0 documents left.

## 1.0.9 — 2026-11-08
- Fixed the persistent "Security token missing or invalid" on uploads/mutations in the embedded preview. Root cause: the session cookie was hard-coded `SameSite=Strict`, which browsers **drop on cross-site iframe API requests**, so the CSRF middleware never received the session cookie and rejected every `POST`/`PATCH`/`DELETE` (a new session was auto-provisioned on each request — 59 rows observed).
- Added `COOKIE_SAMESITE` (`strict` default / `lax` / `none`). `none` is for cross-site iframe hosting only and automatically forces `Secure` (browsers require HTTPS for `SameSite=None`). CSRF token + Origin checks are unchanged; the secure `strict` default is untouched. Preview `.env` now uses `COOKIE_SAMESITE=none` + `COOKIE_SECURE=true`.
- Added regression test `test_cookie_samesite_policy`; pinned `COOKIE_SAMESITE=strict` in the test conftest so tests ignore the deployment `.env`.
- Tests: backend+engine suite **48 passed**. Verified live: with the session cookie present, `POST /api/documents/upload` returns **202** and the document processes; test document removed afterwards (0 documents).

## 1.0.8 — 2026-11-08
- Fixed "Security token missing or invalid" in no-login mode: when an auto-provisioned owner session looked idle-expired, a background poll used to mint a brand-new session (new cookie + CSRF token) while the open page kept the old token, so the next action returned `403 csrf_failed`. `current_session` now refreshes the existing non-revoked owner session **in place** (extends `expires_at`/`last_seen`, keeps the same cookie + CSRF token) before falling back to creating a new one.
- Frontend `api()` and `uploadFiles()` now transparently refresh the CSRF token and retry once on `403 csrf_failed` instead of surfacing the error.
- Pinned the test suite to secure mode (`AUTH_DISABLED=false` in `conftest.py`) so tests no longer inherit the deployment `.env`; added regression test `test_auth_disabled_csrf_stable_after_idle`.
- Bumped the service-worker shell cache to `omnifix-shell-v2` so clients pick up the fix cleanly.
- Tests: backend+engine suite **47 passed**, frontend unit **7 passed**, typecheck/build OK. Verified live: after forced idle expiry, the session cookie no longer rotates and `PATCH /api/settings` + `POST /api/auth/logout` succeed with the original CSRF token.

## 1.0.7 — 2026-11-08
- Added opt-in no-login mode: `AUTH_DISABLED=true` removes the OmniFix sign-in page and auto-authenticates the owner (owner session auto-provisioned in `current_session`). Default remains `false` (secure).
- CSRF/Origin checks, owner-scoped authorization and all upload/storage safeguards stay enabled; API logs a startup warning when no-login mode is on; sign-out button hidden in the UI when enabled.
- Added `AUTH_DISABLED` to `.env.example`, README and AI/SECURITY.md with a clear security warning.
- Tests: `test_auth_disabled_auto_login` and `test_auth_enabled_by_default_requires_login`; backend+engine suite **46 passed**, frontend unit **7 passed**, typecheck/build/lint OK.

## 1.0.6 — 2026-11-06
- Added a no-login proxy activation path: `OMNIFIX_ORIGIN` now lives in `wrangler.toml [vars]` (empty default = guard mode). Editing that one line on github.com and committing to `main` triggers Workers Builds to redeploy the proxy automatically — no `wrangler login` or CLI needed.
- Documented the GitHub-edit method and clarified that Access service-token secrets must still be added in the browser dashboard (never committed). Wrangler dry-run confirms the `OMNIFIX_ORIGIN` environment variable binding.

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
