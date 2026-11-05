# Feature matrix

| Area | Status | Evidence / notes |
|---|---|---|
| Single-owner auth, no registration | Implemented & tested | Argon2id, CLI bootstrap, auth/security tests |
| Sessions, CSRF, rate limits, TOTP | Implemented & tested | HttpOnly/SameSite, Origin checks, encrypted TOTP secret, recovery codes |
| Responsive PWA, themes | Implemented & browser-tested | Desktop/mobile Chromium; manifest/SW/icons; physical devices pending |
| Image/PDF upload validation | Implemented & tested | Signature/MIME/decoder/size/page/pixel checks; malicious/oversize/corrupt tests |
| OmniFix engine (one mode) | Implemented & tested | Deterministic OpenCV/Pillow pipeline; visual dataset tests |
| Boundary detection + manual corners | Implemented & tested | Conservative confidence; touch/mouse/keyboard editor; API corner validation |
| Perspective correction | Implemented & tested | Safe margins, low-confidence full-frame preservation |
| Original preservation | Implemented & tested | Read-only sources, SHA-256 before/after, byte-identical tests |
| Before/after previews | Implemented & browser-tested | Original, processed, slider, side-by-side, zoom/full-screen |
| Multi-page management | Implemented & tested | Order, rotation, include/exclude, add, reprocess; sources retained |
| PDF import/export | Implemented & tested | PyMuPDF/pikepdf import; img2pdf export; page-count tests |
| ZIP exports | Implemented & tested | Images, complete, originals; archive integrity tests |
| Background queue/history | Implemented & tested | Separate worker, progress, cancel/retry, durable SQLite jobs |
| Smart Document Naming | Implemented & tested | Local Tesseract + rules; editable preview; German/English/Arabic |
| Private storage & deletion | Implemented & tested | No public static storage; owner-scoped file endpoints |
| Settings/retention/cleanup | Implemented | Validated settings; explicit retention confirmation; periodic temp/export cleanup |
| Docker/Nginx deployment | Config provided, runtime unverified | Docker unavailable in sandbox |
| Dependency vulnerability scan | Passed after upgrades | pip-audit: no known vulnerabilities; npm audit: 0 |
| Physical iPhone/Safari/Edge/Firefox | Not verified | Requires external devices/browsers |
