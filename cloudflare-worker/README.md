# Cloudflare Worker: guard or reverse proxy

This Worker does **not** run OmniFix. OmniFix is a Python/FastAPI + Next.js + SQLite + private-storage application and must run in Docker (or equivalent) on a server/PC.

The Worker has two modes:

1. **Guard mode** — default when `OMNIFIX_ORIGIN` is unset. It serves a static deployment notice so Workers Builds does not fail.
2. **Proxy mode** — when `OMNIFIX_ORIGIN` is set. It forwards requests to an already-running OmniFix origin, usually a Cloudflare Tunnel hostname.

## Proxy mode requirements

- OmniFix is already deployed and healthy at an HTTPS origin, for example `https://scanner.example.com`.
- The origin is reachable by Cloudflare. A Cloudflare Tunnel public hostname pointing to `http://nginx:8080` is recommended.
- The origin's `TRUSTED_HOSTS` includes the origin hostname.
- The origin's `COOKIE_SECURE=true` in production.
- If the origin is protected by Cloudflare Access, create an Access **service token** and configure the Worker to send it.

## Cloudflare variables/secrets

### No-login method (edit on GitHub)

You do **not** need `wrangler login` or the CLI. The origin URL lives in `wrangler.toml` under `[vars]`:

```toml
[vars]
OMNIFIX_ORIGIN = ""
```

1. Open `wrangler.toml` on github.com → click the pencil (Edit).
2. Change `OMNIFIX_ORIGIN = ""` to your URL, e.g. `OMNIFIX_ORIGIN = "https://scanner.example.com"`.
3. Commit to `main`. Workers Builds redeploys automatically — no Cloudflare login, no CLI.

This works because Workers Builds is already connected and authenticated. The origin URL is public in the repo, which is fine for a hostname. **Never put an Access service-token secret here.**

### Access secrets (browser dashboard, no CLI login)

If the origin is protected by Cloudflare Access, the service-token id/secret cannot go in the public repo. Add them once in the browser dashboard (you are already signed in there):

Workers & Pages → `pdf` → Settings → Variables and Secrets → add **Secrets**:

| Name | Type | Required | Example |
|---|---|---:|---|
| `OMNIFIX_ORIGIN` | variable (in `wrangler.toml`) | yes | `https://scanner.example.com` |
| `CF_ACCESS_CLIENT_ID` | secret (dashboard) | only if origin uses Access service auth | Access service token client id |
| `CF_ACCESS_CLIENT_SECRET` | secret (dashboard) | only if origin uses Access service auth | Access service token client secret |

### Optional CLI method (requires Wrangler login)

Wrangler examples:

```bash
npx wrangler secret put OMNIFIX_ORIGIN --name pdf
npx wrangler secret put CF_ACCESS_CLIENT_ID --name pdf
npx wrangler secret put CF_ACCESS_CLIENT_SECRET --name pdf
```

Or use the guided helper (Node 22+, authenticated Wrangler):

```bash
bash scripts/activate-worker-proxy.sh
```

It prompts for the origin and optional Access service token, stores them as Worker secrets, deploys, and verifies `/api/health` through the proxy.

Do **not** commit these values to Git.

## Access warning

If the Worker sends an Access service token to the origin, the Worker can bypass Access on the origin. Therefore the Worker itself must also be protected by Cloudflare Access, or anyone who can reach the Worker can reach OmniFix through the service token.

Recommended pattern:

1. Protect the Tunnel hostname with Cloudflare Access.
2. Create an Access service token with permission to that application.
3. Protect the Worker hostname with Cloudflare Access too.
4. Configure the Worker with the service-token id/secret.

## Upload limits

Proxy mode is still subject to Cloudflare request-body limits. On free/pro plans, keep OmniFix/Cloudflare upload limits at or below 90 MB if you need reliable uploads through the Worker. For the raised 500 MB request limit, use the Docker/Tunnel deployment directly rather than the Worker proxy.

## Local test

```bash
npx wrangler dev --port 8787 --var OMNIFIX_ORIGIN:http://127.0.0.1:8000
```

Then open `http://127.0.0.1:8787`.
