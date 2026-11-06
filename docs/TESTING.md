# Testing and QA

## Commands
```bash
bash scripts/test.sh
OWNER_PASSWORD='...' npm run test:e2e --prefix frontend
.venv/bin/python scripts/generate_test_dataset.py
.venv/bin/pip-audit -r backend/requirements.lock
(cd frontend && npm run lint && npm audit)
```

`npm run lint` uses ESLint 9 flat config with `eslint-config-next`. It must exit with 0 errors. Existing style/type warnings are tracked separately; private authenticated previews intentionally use `<img>` rather than a shared image optimizer.

## Backend / security (`backend/tests`)
- Auth login/logout/session expiry/revocation, CSRF, cross-origin rejection, rate limits.
- No public registration; protected endpoints fail closed; IDOR; path traversal; unauthorized downloads.
- Malicious signature mismatch, unsupported/corrupt/oversized images, invalid PDF, total request size limit, batch page limit.
- Argon2id password change; TOTP enable/login/recovery codes; security headers.
- Upload/process/original byte integrity/determinism; multi-page order/rotation/inclusion/corners.
- PDF import/export page count; ZIP integrity; smart naming/manual override; job cancel/retry/history; deletion; settings/dashboard.

## Engine / visual (`processing/tests`)
Synthetic dataset: normal, tilted, shadow-heavy, uneven illumination, faint handwriting, colored stamps, signature, small text/complex table, multi-page PDF. Tests verify original bytes unchanged, deterministic output checksums, valid dimensions, perspective behavior, faint-mark/color preservation and visual baseline mean/std/shape. OCR is not used as the preservation oracle.

## Frontend unit (`frontend/tests/unit`)
Authentication screen, upload selection/API invocation, original/processed/slider preview, document rename/delete/export actions, accessible progress/status, CSRF/same-origin API client.

## Browser E2E (`frontend/tests/e2e`)
Desktop Chromium (1440×1000) and mobile Chromium (Pixel 5): real login → upload → worker processing → compare → smart naming → PDF export → download → dashboard; checks no horizontal overflow. Screenshots/traces retained on failure.

## Not executed here
Docker build/runtime, Nginx runtime, physical iPhone Safari, Android Chrome device, desktop Safari/Edge/Firefox. These require external environments and are listed as pending in AI/TODO.md.
