# Changelog

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
