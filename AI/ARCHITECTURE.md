# Architecture

## Processes
1. FastAPI serves the authenticated REST API and the statically exported Next.js shell on one origin.
2. A separate Python worker polls durable SQLite jobs. One page is processed at a time by default; cancellation is cooperative at page boundaries.
3. SQLite (WAL, foreign keys) stores metadata and opaque session-token hashes, never document pixels or OCR text.
4. A private local filesystem stores immutable uploaded sources, PDF reference renders, processed images, thumbnails, OCR text and exports in separate directories.

## Request flow
Browser → same-origin `/api` → session + CSRF + origin validation → owner-scoped query → bounded upload / durable job → worker → local OmniFix pipeline + OCR → private file endpoint → preview/export.

Next.js development uses a server-side rewrite to FastAPI. Production uses FastAPI to serve the static build, avoiding a second public service and cross-origin credentials. The exported shell contains no private data; all document data and files require a valid owner session.

## OmniFix engine
Independent deterministic OpenCV/Pillow/NumPy pipeline: EXIF orientation → lighting/shadow analysis → conservative quadrilateral detection → optional safe perspective correction → adaptive LAB illumination normalization → gentle local contrast, color-preserving enhancement and sharpening → high-quality JPEG. One mode only; intensity scales the same pipeline. No generative model, threshold preset, object removal or content reconstruction.

## Smart naming
Local Tesseract (deu/eng/ara) → multilingual transparent keyword rules → visible type/organization/date extraction → safe German-default filename suggestion → owner review/edit → export. OCR never changes pixels. Unknown content gets a conservative name; upload-year fallback is explicitly identified as upload metadata, not a detected document date.

## Security boundaries
Single owner created by CLI; Argon2id; opaque random sessions stored hashed; HttpOnly/SameSite cookies; double-submit CSRF plus Origin checks; login throttling; optional encrypted TOTP secrets and hashed recovery codes; parameterized SQLAlchemy queries; random storage keys; extension/signature/decoder validation; decompression and page limits; no public static storage route.

## Deployment
Loopback-bound Docker Compose by default. Nginx is the only exposed port; API and worker are internal. Explicit LAN override and VPN guidance are documented. Production requires an explicit random secret and secure-cookie configuration.
