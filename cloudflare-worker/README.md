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

Set these on the Worker (`pdf`) in the Cloudflare dashboard under **Settings → Variables and Secrets**, or with Wrangler:

| Name | Type | Required | Example |
|---|---|---:|---|
| `OMNIFIX_ORIGIN` | variable or secret | yes | `https://scanner.example.com` |
| `CF_ACCESS_CLIENT_ID` | secret | only if origin uses Access service auth | Access service token client id |
| `CF_ACCESS_CLIENT_SECRET` | secret | only if origin uses Access service auth | Access service token client secret |

Wrangler examples:

```bash
npx wrangler secret put OMNIFIX_ORIGIN --name pdf
npx wrangler secret put CF_ACCESS_CLIENT_ID --name pdf
npx wrangler secret put CF_ACCESS_CLIENT_SECRET --name pdf
```

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
