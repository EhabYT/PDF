# Changelog

## 1.0.14 — 2026-11-08
- **Docker deployments silently ignored the new cookie/origin settings.** `docker-compose.yml` passed `COOKIE_SECURE` but not `COOKIE_SAMESITE`, `COOKIE_FALLBACK_HEADER` or `ALLOW_OPAQUE_ORIGIN`, so anyone deploying via Compose (the documented production path) could set them in `.env` and see no effect. All three now pass through with secure defaults, and `AUTH_DISABLED` reaches the worker too.
- Full-app audit pass (every route, page-editing actions, all four export formats, security and storage endpoints) run as a real user through a sandboxed iframe and over the API:
  - All 8 routes render with no console or page errors and no failed requests.
  - Document lifecycle verified end-to-end: multi-page upload, reorder, all four rotations, include/exclude (source files preserved), normalized corner editing, detect, reprocess, process-all, add-pages, rename.
  - All four exports produce valid files: PDF (`%PDF-` header, A4 595.276pt), `images` ZIP, `zip` bundle (PDF + page JPEGs + document.json), `originals` ZIP (byte-identical PNGs).
  - Correctly rejected as designed: pixel-space corners (must be normalized 0–1), wrong export format names, and concurrent mutations while a job is active (409 job_active — the UI guards this with its busy state).
- Tests remain **56 passed**; no behavioural regressions found.

## 1.0.13 — 2026-11-08
- Fixed two navigation bugs found by driving the real UI in a sandboxed iframe with headless Chromium:
  - **`HEAD` returned 405** on every page route. Next.js issues HEAD when prefetching, so client routing was degraded. The shell route now serves GET and HEAD.
  - **Embedded CORS was incomplete.** In an opaque-origin embed every request is preflighted, so (a) Next.js RSC headers were rejected — including `next-router-segment-prefetch`, which I had missed — killing link prefetch, and (b) **Private Network Access** preflights (`Access-Control-Request-Private-Network`, since the embed fetches a loopback address) returned **400** because Starlette needs `allow_private_network`. Both now enabled under the same `ALLOW_OPAQUE_ORIGIN` + `AUTH_DISABLED` opt-in via `allow_private_network=True`.
- Extracted `cors_configuration()` from `main.py` so the embedded-preview CORS policy is unit-testable (middleware is built once at import, so settings monkeypatching could not verify it).
- Tests: **56 passed**, incl. `test_embedded_cors_allows_next_router_headers`, `test_embedded_cors_off_by_default`, `test_head_requests_served_for_client_routing`.
- Verified in the sandboxed iframe: **no CORS or console errors**, `RESULT {"rsc":"200 cors","plain":"200 cors","api":"200 cors"}`, upload 202, document page opens.

## 1.0.12 — 2026-11-08
- Added `scripts/preflight.sh` and wired it into `scripts/setup.sh` and `scripts/start.sh`. Missing **system** packages (tesseract + `deu`/`eng`/`ara`, libmagic) previously caused OCR/Smart Document Naming to fail silently at job time; setup and start now fail loudly with copy-paste install commands for Debian, Fedora and Alpine. `ALLOW_MISSING_OCR=1` downgrades it to a warning for users who only want scanning.
- Verified the guard both ways: exits 1 with tesseract absent, exits 0 with `ALLOW_MISSING_OCR=1`, exits 0 when everything is present.
- Documented in README requirements.
- Re-verified end-to-end after a clean environment rebuild: upload → **202**, pipeline completes, OCR naming produces `Mietvertrag_Hausverwaltung_Schmidt_GmbH_03-2026` (German, "Rental Agreements"), original/processed/thumbnail all **200**.

## 1.0.11 — 2026-11-08
- Fixed the **real** cause of the embedded-preview failures, found by reproducing the host with a real browser: a sandboxed iframe **without `allow-same-origin` has the opaque origin `"null"`**. In that context `document.cookie` and `localStorage` **throw**, and the browser treats every request as cross-origin, so `/api/*` responses arrive at the server but are withheld from JavaScript unless `Access-Control-Allow-Origin: null` is returned. The app therefore fell back to the sign-in page and every mutation failed.
- Added `ALLOW_OPAQUE_ORIGIN` (default `false`): accepts `Origin: null` in the CSRF/Origin middleware **and** adds `null` to the CORS allowlist. Honoured only when `AUTH_DISABLED=true`; the CSRF token is still mandatory, and any real foreign origin is still rejected.
- Tests: **53 passed**, incl. `test_opaque_origin_opt_in` (also asserts a foreign origin is still rejected with the opt-in on) and `test_opaque_origin_never_allowed_with_real_login`. Pinned both new flags in the test conftest so the deployment `.env` cannot leak into tests.
- Verified in a real browser inside a cross-site `sandbox="allow-scripts"` iframe: app auto-authenticates, `POST /api/documents/upload` → **202**, document page renders with original/processed/thumbnail all **200**, OCR naming applied.

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
