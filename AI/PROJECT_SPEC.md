# Project specification

## Product
OmniFix Private Scanner is a single-owner, private web application for uploading photographs/PDFs, enhancing document pages with one independent OmniFix-inspired deterministic pipeline, reviewing originals vs outputs, and exporting PDFs/images/ZIPs. It is not public SaaS.

## Non-negotiable priorities
1. Privacy and security; no public registration, tracking, cloud uploads or external AI.
2. Original preservation: immutable sources, SHA-256 verification, separate outputs, no generative reconstruction or intentional content removal.
3. One OMNIFIX mode only; adaptive illumination, conservative detection, safe perspective, natural color/detail.
4. Multi-page management, manual corners, before/after inspection, professional PDF export.
5. Local OCR Smart Document Naming (German default, English/Arabic), editable suggestions, no invented facts.
6. Responsive mobile/desktop PWA, durable background jobs, private storage, tests and deployment docs.

## Functional scope
- Auth: Argon2id, sessions, CSRF, rate limits, optional TOTP, CLI bootstrap, password/session management.
- Upload: JPG/JPEG/PNG/WebP/TIFF/PDF; drag/drop, file picker, camera input; signature/MIME/size/page/pixel validation.
- Processing: detect boundaries, correct perspective when confident, enhance, thumbnail, OCR, classify/name.
- Library: search/filter/sort/rename/delete/export; page order/rotation/inclusion/reprocess/add.
- Export: processed PDF (A4 default), processed images ZIP, complete ZIP, originals ZIP; owner-approved filename.
- Settings: general/theme/language, processing intensity/toggles/resolution, storage/retention/cleanup.
- History: job status/progress/page progress/cancel/retry/errors.

## Acceptance evidence
See AI/STATUS.md, AI/FEATURE_MATRIX.md and docs/TESTING.md. Do not mark external checks (Docker host, physical devices) complete without running them.
