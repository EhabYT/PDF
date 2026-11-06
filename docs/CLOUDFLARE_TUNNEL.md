# Private Cloudflare Tunnel setup

This guide exposes OmniFix through Cloudflare Tunnel **without opening inbound public ports** on the server. The tunnel hostname should be protected by **Cloudflare Access** so only the owner can reach the application. The app’s own login remains enabled as a second layer.

> A Cloudflare Tunnel public hostname creates public DNS. “Private” here means the origin is not directly reachable and Access gates the hostname. If you need no public hostname at all, use Cloudflare WARP private routing / a private network instead.

## 1. Prepare the application environment

### Helper script

On the Docker host, from the repository root:

```bash
bash scripts/deploy-cloudflare.sh
```

The script prompts for the public hostname and tunnel token, generates `SESSION_SECRET`, writes `.env`, starts the Compose stack with cloudflared, waits for API health and runs owner bootstrap. It does not create Cloudflare Access policies; do that in the dashboard.

### Manual `.env`

In `.env`:

```env
ENVIRONMENT=production
SESSION_SECRET=<random 64-hex secret>
COOKIE_SECURE=true
TRUSTED_HOSTS=scanner.example.com,localhost,127.0.0.1
ALLOWED_ORIGINS=https://scanner.example.com
BIND_ADDRESS=127.0.0.1
HTTP_PORT=8080
TUNNEL_TOKEN=<cloudflare tunnel token>
# Cloudflare free/pro plans cap request bodies at 100 MB:
MAX_UPLOAD_MB=90
MAX_PDF_MB=90
```

Replace `scanner.example.com` with your hostname. Keep `BIND_ADDRESS=127.0.0.1` so Nginx is not published on a public interface.

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 2. Create the tunnel

Cloudflare Zero Trust dashboard:

1. **Networks → Tunnels → Create a tunnel**.
2. Choose **Cloudflared**.
3. Name it, e.g. `omnifix-private-scanner`.
4. Copy the tunnel token into `.env` as `TUNNEL_TOKEN`.

### Docker deployment

Add a public hostname in the tunnel dashboard:

- Hostname: `scanner.example.com`
- Service: `http://nginx:8080`

Then run:

```bash
docker compose -f docker-compose.yml -f deployment/cloudflare/docker-compose.cloudflare.yml up -d --build
docker compose exec api python -m app.bootstrap --username owner
```

The `cloudflared` container joins the internal Compose network and reaches Nginx at `nginx:8080`. The host still binds Nginx only to loopback.

### Host-managed cloudflared

If cloudflared runs on the host instead of Docker, point the tunnel service to:

```text
http://127.0.0.1:8080
```

and run the normal Compose stack:

```bash
docker compose up -d --build
cloudflared tunnel run --token <TUNNEL_TOKEN>
```

## 3. Protect the hostname with Cloudflare Access

Zero Trust dashboard:

1. **Access → Applications → Add application → Self-hosted**.
2. Application name: `OmniFix Private Scanner`.
3. Session duration: e.g. 12–24 hours.
4. Add the public hostname `scanner.example.com`.
5. Create an **Allow** policy:
   - Include: **Emails** → your owner email address.
   - Optionally require MFA / your identity provider.
6. Save.

Do **not** create a broad “Allow everyone” policy. The tunnel alone is not authentication.

## 3b. Optional: proxy the Cloudflare Worker to this Tunnel hostname

The repository Worker can forward traffic to an already-running OmniFix origin instead of showing the static notice. This is optional; the simplest private deployment is to use the Tunnel hostname directly.

Set these Worker variables/secrets on the `pdf` Worker:

```text
OMNIFIX_ORIGIN=https://scanner.example.com
CF_ACCESS_CLIENT_ID=<Access service token id, only if the origin uses Access>
CF_ACCESS_CLIENT_SECRET=<Access service token secret, only if the origin uses Access>
```

If the origin is protected by Cloudflare Access and the Worker uses a service token, protect the Worker hostname with Cloudflare Access too. Otherwise the Worker becomes a public bypass around the origin's Access policy.

Guided activation from any machine with Node 22+ and authenticated Wrangler:

```bash
bash scripts/activate-worker-proxy.sh
```

Proxy mode remains subject to Cloudflare request-body limits. For uploads above the Cloudflare free/pro body cap, use the Tunnel hostname directly instead of the Worker proxy.

## 4. Verify

```bash
curl -I https://scanner.example.com/api/health
```

Expected behavior:

- Without Cloudflare Access session: redirect to Access login.
- After Access login: app login page appears.
- After app login: dashboard works.
- Unauthenticated API requests still return 401.
- Direct access to the server’s public IP on port 8080 should fail because the bind is loopback-only.

## 5. Security checklist

- [ ] Cloudflare Access policy allows only the owner email / IdP group.
- [ ] App owner password is strong and unique.
- [ ] Optional app TOTP is enabled.
- [ ] `COOKIE_SECURE=true` because the browser origin is HTTPS.
- [ ] `TRUSTED_HOSTS` contains the exact tunnel hostname.
- [ ] `BIND_ADDRESS=127.0.0.1`; no public inbound port.
- [ ] Tunnel token and `.env` are not committed.
- [ ] cloudflared image is pinned to a digest after validation.
- [ ] Backups remain encrypted and off-device.

## Troubleshooting

| Symptom | Fix |
|---|---|
| 400 Bad Request / invalid host | Add the tunnel hostname to `TRUSTED_HOSTS`. |
| CSRF / origin rejected | Use the exact HTTPS hostname; set `ALLOWED_ORIGINS=https://scanner.example.com` if needed. |
| Login cookie not stored | Ensure `COOKIE_SECURE=true` and the browser URL is HTTPS. |
| Access login loops | Check Access application hostname and policy; clear Access cookies. |
| 502 from tunnel | Ensure service URL is `http://nginx:8080` for Docker or `http://127.0.0.1:8080` for host cloudflared; check Nginx/API health. |
| Upload fails through tunnel | Cloudflare has request body limits by plan; keep uploads within plan limits or use VPN for very large documents. |
