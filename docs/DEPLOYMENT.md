# Deployment guide

## Local production-style
```bash
bash scripts/setup.sh
bash scripts/bootstrap.sh
bash scripts/start.sh
```
FastAPI serves the built Next.js shell and API on one origin. Default bind is 127.0.0.1.

## Docker Compose
```bash
cp .env.example .env
# Set SESSION_SECRET to a random 64-hex value; keep BIND_ADDRESS=127.0.0.1.
docker compose up --build -d
docker compose exec api python -m app.bootstrap --username owner
```
Services: `api` (internal 8000), `worker` (no ports), `nginx` (published 127.0.0.1:8080 by default). The backend image builds the frontend in a Node stage, installs pinned Python dependencies and Tesseract, runs migrations on startup, and runs as a non-root user. Storage is a bind mount.

Validate on your Docker host:
```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f api worker
```
Docker was unavailable in the development sandbox; these commands were not executed there.

## Environment
See `.env.example`. Important values:
- `SESSION_SECRET`: required in production; generate randomly, never commit.
- `COOKIE_SECURE`: false for plain-HTTP loopback/LAN; true behind HTTPS.
- `TRUSTED_HOSTS`: exact hostnames; avoid `*` outside development.
- `ALLOWED_ORIGINS`: empty by default (same-origin only).
- `BIND_ADDRESS`: 127.0.0.1 default; set explicitly for LAN/VPN interface.
- Size/page/pixel/worker limits: tune to host RAM. Defaults are 50 MB/image, 100 MB/PDF, 500 MB/request and 300 pages; the included Nginx upload locations allow 500 MB. Behind Cloudflare free/pro, set `MAX_UPLOAD_MB=90` and `MAX_PDF_MB=90` because Cloudflare caps request bodies at 100 MB.

## LAN / VPN
- LAN: set `BIND_ADDRESS` to the LAN interface, firewall to trusted clients only, use strong credentials. HTTP is unencrypted.
- Tailscale/WireGuard: bind to the VPN address or tunnel to loopback. Prefer HTTPS for browser Secure cookies and PWA installability on remote origins.
- SSH tunnel: `ssh -L 8080:127.0.0.1:8080 user@server`.

## Updating
Back up first, update source/locks, rebuild images or run setup/build, apply Alembic migrations, restart, run tests. Do not delete the storage volume during updates.

## Reverse proxy / TLS
The included Nginx proxies to the internal API and enforces upload body limits. For public-facing TLS (not recommended without VPN), terminate TLS at a trusted proxy, forward Host/X-Forwarded-Proto, set Secure cookies and exact trusted hosts. Never enable public registration.
