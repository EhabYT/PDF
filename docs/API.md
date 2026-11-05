# REST API

Base path: `/api`. Same-origin browser requests; mutating requests require `X-CSRF-Token`. Authenticated endpoints require the owner session cookie. Errors: `{ "error": { "code", "message" } }`. Interactive OpenAPI docs are available at `/api/docs` in development only.

## Authentication
- `GET /auth/session` — session state + CSRF token (pre-auth token when signed out).
- `POST /auth/login` — `{username, password, totp_code?}`.
- `POST /auth/logout`, `POST /auth/logout-all`.
- `POST /auth/password/change` — `{current_password, new_password}`.
- `POST /auth/totp/setup` — provisioning URI + QR SVG.
- `POST /auth/totp/enable`, `POST /auth/totp/disable` — `{password, code}`.

## Documents
- `POST /documents/upload` — multipart `files[]`, `combine`; 202 + documents.
- `GET /documents` — `q, category, sort, date_from, date_to, page, page_size`.
- `GET /documents/{id}` — detail with pages, sources and active job.
- `PATCH /documents/{id}` — `{name?, category?, accept_name?, filename_language?, transliterate?}`.
- `DELETE /documents/{id}` — explicit permanent deletion (blocked while a job is active).
- `POST /documents/{id}/files` — append pages.
- `POST /documents/{id}/process` — queue full document processing.
- `GET /documents/{id}/sources/{source_id}/download` — original uploaded source.

## Pages
- `GET /pages/{id}/file?kind=original|processed|thumbnail` — private image.
- `PATCH /pages/{id}/order` — `{order: [page_ids]}` (complete permutation).
- `PATCH /pages/{id}/rotation` — `{rotation: 0|90|180|270}`.
- `PATCH /pages/{id}/include` — `{included}`; exclusion never deletes the source.
- `PATCH /pages/{id}/corners` — `{corners: [[x,y]×4 normalized], apply}`.
- `POST /pages/{id}/detect` — reset automatic detection.
- `POST /pages/{id}/reprocess`.

## Jobs / history
- `GET /jobs` — `status, page, page_size`.
- `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry`.

## Exports
- `POST /documents/{id}/export/{pdf|images|zip|originals}` — `{filename?, page_size, orientation, quality, page_ids?}`; 202 + job.
- `GET /documents/{id}/exports`.
- `GET /exports/{id}/download` — owner-checked, checksum-verified file.

## Settings / storage / security / dashboard
- `GET /settings`, `PATCH /settings`.
- `GET /storage`, `POST /storage/cleanup` — `{include_documents, confirm}`.
- `GET /security/sessions`, `DELETE /security/sessions/{id}`, `POST /security/sessions/revoke-others`.
- `GET /dashboard` — real statistics, recent documents/jobs and storage usage.
- `GET /health` — public liveness only; no private data.

Filesystem paths, password hashes, session tokens and OCR text are never returned by the API.
