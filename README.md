# OmniFix Private Scanner

A private, single-owner document scanning and enhancement platform inspired by CamScanner. Upload photos or PDFs, detect and correct document boundaries, enhance pages with one deterministic **OmniFix-inspired** pipeline, compare before/after, and export professional PDFs or ZIP archives — without cloud processing, tracking, or generative reconstruction.

> **Important:** CamScanner’s OmniFix is proprietary. This project implements an independent OpenCV/Pillow/NumPy pipeline inspired by its visual goals. It does not copy proprietary code or claim algorithmic equivalence.

## PDF / Cloudflare Tunnel quickstart

This repository contains the full OmniFix Private Scanner source. To run it as a private PDF scanner behind Cloudflare Tunnel:

```bash
git clone https://github.com/EhabYT/PDF.git
cd PDF
cp .env.example .env
```

Edit `.env`:

```env
ENVIRONMENT=production
SESSION_SECRET=<random-64-hex-secret>
COOKIE_SECURE=true
TRUSTED_HOSTS=scanner.yourdomain.com,localhost,127.0.0.1
ALLOWED_ORIGINS=https://scanner.yourdomain.com
BIND_ADDRESS=127.0.0.1
HTTP_PORT=8080
TUNNEL_TOKEN=<your-cloudflare-tunnel-token>
```

Generate the secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

In Cloudflare Zero Trust, create a tunnel and point the public hostname to the internal Docker service:

```text
Hostname: scanner.yourdomain.com
Service:  http://nginx:8080
```

Protect that hostname with a Cloudflare Access self-hosted application that allows only your email/IdP group. Then start the stack and create the owner:

```bash
docker compose -f docker-compose.yml -f deployment/cloudflare/docker-compose.cloudflare.yml up -d --build
docker compose exec api python -m app.bootstrap --username owner
```

Open `https://scanner.yourdomain.com`, pass Cloudflare Access, then sign in to OmniFix. Full tunnel guidance: [docs/CLOUDFLARE_TUNNEL.md](docs/CLOUDFLARE_TUNNEL.md).

## What is included

- Next.js 16 + TypeScript + Tailwind responsive PWA (light/dark/system themes).
- FastAPI REST API with Argon2id single-owner authentication, secure sessions, CSRF, rate limiting and optional TOTP.
- Separate SQLite-backed background worker with progress, cancellation, retry and history.
- Immutable original storage with SHA-256 verification; separate processed files, thumbnails, OCR text and exports.
- Conservative document detection, safe perspective correction, adaptive illumination/shadow correction, gentle contrast/color/detail enhancement.
- Interactive mouse/touch/keyboard corner editor, zoom, full-screen, original/processed/slider/side-by-side previews.
- Multi-page ordering, rotation, inclusion/exclusion, reprocessing, adding pages and renaming.
- PDF import (PyMuPDF/pikepdf) and image-based PDF export (img2pdf), processed image ZIP, complete ZIP and original ZIP.
- Local Tesseract OCR (German/English/Arabic) and conservative rule-based Smart Document Naming with editable suggestions.
- SQLAlchemy/Alembic, Docker Compose, Nginx, automated backend/engine/frontend/browser tests and documentation.

## Requirements

- Python **3.13** (Docker image uses 3.13).
- Node.js **20.9+** (22 recommended) and npm.
- Tesseract OCR with `deu`, `eng`, `ara` models and libmagic for local development.
- Docker + Docker Compose plugin for container deployment.
- ~2 GB RAM minimum for the default worker limits; more for very large PDFs.

Ubuntu/Debian OCR packages:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-ara libmagic1
```

## Quick start — local development

```bash
cd omnifix-private-scanner
bash scripts/setup.sh          # venv, pinned dependencies, .env with random secret, migrations
bash scripts/bootstrap.sh      # prompts for a new owner password (no default password)
bash scripts/dev.sh            # API on http://127.0.0.1:8000 + background worker
```

For frontend hot reload, run in a second terminal:

```bash
cd frontend
npm run dev                    # http://127.0.0.1:3000, proxies /api to FastAPI
```

For a production-style local run (builds the frontend and serves everything from FastAPI):

```bash
bash scripts/start.sh
```

Open **http://127.0.0.1:8000**, sign in with the owner account, and choose **NEW SCAN**.

## First-time owner setup

There is **no public registration**. Create exactly one owner through the CLI:

```bash
bash scripts/bootstrap.sh --username owner
```

The command prompts twice for a password of at least 12 characters. It refuses to create another account if any owner already exists. To automate securely, supply `OMNIFIX_BOOTSTRAP_PASSWORD` from your secret manager; never commit it. Change the password later in **Security**.

## Docker deployment (private by default)

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # put output in SESSION_SECRET
# Edit .env: keep BIND_ADDRESS=127.0.0.1 for loopback-only access.
docker compose up --build -d
docker compose exec api python -m app.bootstrap --username owner
```

Open **http://127.0.0.1:8080**. Nginx is the only published port; API and worker stay on the internal Docker network. Compose binds to loopback unless you explicitly change `BIND_ADDRESS`.

> Docker was not available in the development sandbox, so the container build/runtime is provided but **not executed here**. Validate it on your Docker host before production use.

## Private network and remote access

- **Localhost only (default):** `BIND_ADDRESS=127.0.0.1`.
- **Explicit LAN:** set `BIND_ADDRESS=0.0.0.0` (or a LAN interface address), restrict access with your firewall, and use a strong owner password. Plain HTTP on a LAN is not encrypted.
- **Cloudflare Tunnel:** see [docs/CLOUDFLARE_TUNNEL.md](docs/CLOUDFLARE_TUNNEL.md). Keep the origin loopback-only and protect the tunnel hostname with Cloudflare Access.
- **Remote:** prefer WireGuard/Tailscale. Bind to the VPN interface address or keep loopback and use an SSH tunnel:
  ```bash
  ssh -L 8080:127.0.0.1:8080 user@private-server
  ```
- For HTTPS, terminate TLS at a trusted reverse proxy, set `COOKIE_SECURE=true`, and add the exact hostname to `TRUSTED_HOSTS` and `ALLOWED_ORIGINS` if cross-origin access is truly needed.
- Do not expose this application directly to the public internet. There is no public registration, but defense in depth still matters.

## Using the application

1. **New Scan:** drag/drop, browse files, or use the mobile camera input. Combine images into one document or keep unrelated files separate. PDFs remain multi-page documents.
2. **Processing:** the worker detects boundaries, corrects perspective only when confident, applies OmniFix enhancement, generates thumbnails and runs local OCR.
3. **Document workspace:** compare original/processed, drag corners (touch and keyboard supported), rotate, reorder, exclude pages, add pages or reprocess.
4. **Smart naming:** review the suggested filename, category, detected type, organization, date and purpose. Edit before export; nothing is forced.
5. **PDF Export:** choose A4/Letter/Legal/original dimensions, orientation and quality. Export processed PDF, processed images ZIP, complete ZIP or original files ZIP.
6. **Documents / History:** search, filter, rename, delete, retry/cancel jobs and download previous exports.
7. **Settings / Security:** language, theme, processing intensity, retention, password, sessions and optional TOTP.

## OmniFix processing and preservation

One mode only: **OMNIFIX**. Intensity scales the same adaptive pipeline; there are no alternate filters. Stages: orientation/lighting analysis → edge/contour quadrilateral detection → safe perspective correction → LAB illumination normalization → bounded white balance, mild local contrast, denoising and sharpening → high-quality JPEG.

Original uploaded files are never overwritten. They are stored read-only, checksummed, and verified before and after processing. Enhancement and perspective correction cannot guarantee pixel-level preservation of the **output**; the guarantee is that source files remain intact and the pipeline does not intentionally remove, rewrite or invent document information. No generative AI is used.

See [docs/PROCESSING.md](docs/PROCESSING.md).

## Smart Document Naming

Local Tesseract OCR recognizes visible text; transparent multilingual rules classify document purpose and extract only visible organization/date evidence. Default filename language is German, with English/Arabic options and Arabic transliteration. Unknown documents get `Unbekanntes_Dokument_<upload-year>.pdf`; the upload year is explicitly labeled as upload metadata, not a detected document date. OCR never modifies pixels. See [docs/SMART_NAMING.md](docs/SMART_NAMING.md).

## Backups

```bash
bash scripts/backup.sh
```

Creates a timestamped archive containing a consistent SQLite snapshot and private storage. Store backups encrypted off-device. Stop the worker before restoring. See [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md).

## Testing

```bash
bash scripts/test.sh
# Browser tests against a running instance:
OWNER_PASSWORD='your-owner-password' npm run test:e2e --prefix frontend
```

Current verified results are recorded in [AI/STATUS.md](AI/STATUS.md) and [docs/TESTING.md](docs/TESTING.md). Synthetic visual datasets cover tilted, shadowed, unevenly lit, faint-handwriting, stamp/signature, small-text/table and multi-page cases.

## Troubleshooting

| Symptom | Check |
|---|---|
| Login fails after deployment | `SESSION_SECRET` set; `COOKIE_SECURE` matches HTTP/HTTPS; hostname in `TRUSTED_HOSTS`; clock correct for TOTP. |
| Upload rejected | Extension must match signature; image/PDF size, page count and pixel limits; PDF must be unencrypted; multi-frame TIFF/WebP must be split. |
| Pages stay queued | Worker process/container running; storage writable; check worker logs for resource limits. |
| OCR naming unavailable | Install `tesseract-ocr-deu` and `tesseract-ocr-ara`; verify `tesseract --list-langs`. |
| Boundary not cropped | Confidence was low by design. Use **Adjust corners**; the full original is preserved. |
| Export has margins | A4 fitting preserves aspect ratio without cropping; choose **Original image dimensions** for edge-to-edge pages. |
| Docker build fails | Validate on a Docker host; this sandbox could not execute Docker. |

## Security

Argon2id passwords, hashed opaque sessions, HttpOnly/SameSite cookies, CSRF + Origin checks, login throttling, optional encrypted TOTP, owner-scoped queries, random storage keys, strict upload validation, decompression/page/pixel limits, security headers, no public storage URLs, no analytics. Run `pip-audit -r backend/requirements.lock` and `npm audit` before deployment. See [AI/SECURITY.md](AI/SECURITY.md).

## Updating

1. Back up storage and database.
2. Pull/update source and review dependency changes.
3. `pip install -r backend/requirements.lock`, `npm ci`, `npm run build`.
4. `cd backend && alembic upgrade head`.
5. Restart API and worker; run tests and verify login/upload/export.

## Project structure

```text
backend/          FastAPI app, models, security, services, worker, migrations, tests
frontend/         Next.js app, components, PWA assets, unit/browser tests
processing/       OmniFix engine, PDF import/export, OCR/naming, visual tests
storage/          Private originals, processed files, thumbnails, temp, exports (gitignored)
deployment/       Dockerfiles, Nginx, healthcheck
scripts/          Setup, bootstrap, dev/start, test, backup, dataset generation
docs/             Deployment, API, processing, naming, backup, testing, limitations
AI/               Specification, architecture, decisions, security, status, TODO, changelog
```

## Known limitations

- Docker runtime and physical iPhone/Safari/Edge/Firefox device testing are not verified in this sandbox; desktop/mobile Chromium automated tests pass.
- Processed PDFs are image-based; no OCR-searchable text layer is added.
- OCR/classification is local and rule-based, not semantic AI; unclear documents require review.
- Encrypted PDFs and multi-frame TIFF/WebP are rejected with clear errors.
- Interface language switching localizes navigation and common controls; some long explanatory text remains English.
- Automatic document retention deletion is opt-in and requires explicit confirmation.

## License / privacy

Private personal-use project. No advertising, tracking, analytics, external image uploads, third-party AI processing or external storage by default. Keep your server, `.env`, database and storage private.
