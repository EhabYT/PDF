# Fixing the Cloudflare `wrangler deploy` build error

## Error

```text
Executing user deploy command: npx wrangler deploy
✘ [ERROR] Could not detect a directory containing static files (e.g. html, css and js) for the project
Failed: error occurred while running deploy command
```

## Cause

Cloudflare is trying to deploy this repository as a **Cloudflare Worker/static-assets project** using:

```bash
npx wrangler deploy
```

This repository is a full-stack monorepo:

```text
frontend/   Next.js static frontend
backend/    Python FastAPI API
processing/ OpenCV/Pillow/PyMuPDF processing engine
storage/    private local filesystem storage
```

It is **not** a Worker-only static site, and the Python backend cannot run as a normal Cloudflare Worker. There is no root static assets directory for Wrangler to deploy, so the deploy command fails.

## Correct fix for the full application

Use **Cloudflare Tunnel** in front of the Docker deployment, not Cloudflare Workers Builds.

1. Run OmniFix on a private server/host with Docker:

   ```bash
   docker compose -f docker-compose.yml -f deployment/cloudflare/docker-compose.cloudflare.yml up -d --build
   docker compose exec api python -m app.bootstrap --username owner
   ```

2. In Cloudflare Zero Trust, create a Tunnel public hostname pointing to:

   ```text
   http://nginx:8080
   ```

   If `cloudflared` runs on the host instead of Docker, use:

   ```text
   http://127.0.0.1:8080
   ```

3. Protect the hostname with Cloudflare Access.

4. Open the tunnel hostname in the browser.

Full guide: [CLOUDFLARE_TUNNEL.md](CLOUDFLARE_TUNNEL.md).

## If you already created a Workers/Pages build

Disable or delete the failing Workers build:

```text
Cloudflare dashboard → Workers & Pages → select the failing project → Settings → Builds / Deployments → disconnect or delete
```

Do not use `npx wrangler deploy` for the full OmniFix application.

## Optional: frontend-only Cloudflare Pages deployment

You can host only the static frontend on Cloudflare Pages, but it will **not** process documents unless it can reach a running OmniFix backend. This is not the recommended private deployment.

If you still want a frontend-only Pages project:

```text
Framework preset: Next.js (static export) or None
Root directory: frontend
Build command: npm ci && npm run build
Build output directory: out
Node version: 22
Environment variable: NEXT_TELEMETRY_DISABLED=1
```

Do not use `npx wrangler deploy` for Pages; use Cloudflare Pages deployment. The app’s `/api` calls will fail unless you separately provide a compatible backend and adjust CORS/cookies/origin configuration.

## Recommended conclusion

For OmniFix Private Scanner, the supported Cloudflare path is:

```text
Browser → Cloudflare Access → Cloudflare Tunnel → Nginx → FastAPI + worker + private storage
```

not:

```text
Cloudflare Workers → npx wrangler deploy
```
