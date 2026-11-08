# Security implementation and audit summary

Date: 2026-11-05

## Controls
- Single owner via CLI bootstrap; no registration endpoint; second bootstrap refused.
- Argon2id (time_cost=3, memory_cost=64 MiB, parallelism=2); dummy hash for missing users; rehash on login when parameters change.
- Opaque 256-bit session tokens stored as SHA-256 hashes; HttpOnly cookies; SameSite configurable via `COOKIE_SAMESITE` (default `strict`, most protective); Secure flag configurable and forced on when `SameSite=None`; 12 h absolute / 60 min idle expiry; revocation and logout-all. `SameSite=None` exists only for cross-site iframe/embedded-preview hosting, where a `Strict` cookie would be dropped by the browser and every mutation would fail CSRF; it requires HTTPS and does not disable the CSRF token or Origin checks. Covered by `test_cookie_samesite_policy`.
- CSRF token required on all mutating API requests; login uses a pre-auth double-submit token; Origin validated against request host or explicit allowlist.
- Login rate limits per IP and global; password/TOTP change throttling.
- Optional TOTP with encrypted secret (Fernet derived from deployment secret) and hashed one-time recovery codes.
- Owner authorization on every document/page/job/export/source/file query; guessed IDs return 404.
- SQLAlchemy parameterized queries; no client-supplied filesystem paths; random storage keys; path resolution constrained to storage root.
- Upload extension + signature + libmagic MIME + Pillow decoder + PDF parser validation; size/page/pixel limits; encrypted PDFs and multi-frame images rejected.
- Worker memory limit, per-page timeout, single concurrency, OpenCV/BLAS thread limits; PDF rasterization pixel cap prevents decompression bombs.
- Security headers: CSP, nosniff, referrer-policy, permissions-policy, frame restrictions in production; HSTS when Secure cookies enabled.
- Private files served only through authenticated endpoints with `Cache-Control: private, no-store`; PWA caches public shell/static assets only.
- No analytics/telemetry by default; Next telemetry disabled in build scripts; no external OCR/AI/storage.
- Errors return safe codes/messages; logs record exception types, not document contents or stack traces to users.

## Optional no-login mode (opt-in, off by default)
`AUTH_DISABLED=true` removes the sign-in page and transparently authenticates the single owner (`current_session` auto-provisions an owner session). This **disables authentication**: anyone who can reach the URL has full owner access. It is intended only for deployments already protected by Cloudflare Access, a VPN, or a trusted private network. CSRF and Origin checks remain enabled; owner-scoped authorization and all upload/storage safeguards are unchanged. The API logs a startup warning when enabled. Default is `false`. Covered by `test_auth_disabled_auto_login` and `test_auth_enabled_by_default_requires_login`.

## Tests
Authentication, session expiry/revocation, CSRF, cross-origin rejection, login throttling, IDOR, path traversal, malicious/corrupt/oversized uploads, invalid PDF, unauthorized downloads, TOTP, password change, security headers, private storage access and the opt-in no-login mode are covered in `backend/tests/test_security.py`.

## Dependency audit
Initial scans found vulnerabilities in Pillow, cryptography, python-multipart, pydantic-settings, pytest, Next.js, PostCSS and Vitest/tinypool. Dependencies were upgraded and locks regenerated.

Final scans:
- `pip-audit -r backend/requirements.lock`: **No known vulnerabilities found**.
- `npm audit` (frontend, including dev dependencies): **0 vulnerabilities**.

## Residual risks / deployment responsibilities
- Plain HTTP on loopback/LAN is not encrypted; use HTTPS or a private VPN for remote access.
- Keep `.env`, SQLite DB and storage private and backed up. File permissions and host security are the operator’s responsibility.
- Docker runtime, Nginx runtime and physical-device browsers were not executed in this sandbox.
- CSP allows inline Next.js bootstrap scripts/styles; no external script origins are allowed.
- Rate limiting is local SQLite, appropriate for single-owner deployment, not a distributed WAF.
- Original preservation is byte-level for uploaded sources; enhanced outputs are not pixel-identical by design.
