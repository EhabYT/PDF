#!/usr/bin/env bash
# OmniFix Private Scanner — one-command Cloudflare Tunnel deployment.
#
# Run this on the machine that will host the app (your PC or a VPS):
#
#   bash scripts/deploy-cloudflare.sh
#
# It will ask for your public hostname and Cloudflare Tunnel token, generate a
# strong SESSION_SECRET, write a production .env, start the Docker stack with
# cloudflared, wait for health, and create the owner account.
#
# Prerequisites: Docker + Docker Compose plugin, and a Cloudflare Tunnel whose
# public hostname points to http://nginx:8080 (see docs/CLOUDFLARE_TUNNEL.md).
set -euo pipefail
cd "$(dirname "$0")/.."

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die() { printf '\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

bold "OmniFix Private Scanner — Cloudflare Tunnel deployment"

# 1. Prerequisites -----------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install it first:  curl -fsSL https://get.docker.com | sudo sh"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is missing. Install Docker Desktop or the docker-compose-plugin package."
docker info >/dev/null 2>&1 || die "Docker daemon is not running or your user lacks permission. Start Docker, or run: sudo usermod -aG docker \$USER (then re-login)."

# 2. Inputs ------------------------------------------------------------------
CF_HOSTNAME="${CF_HOSTNAME:-}"
CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN:-}"

if [[ -z "$CF_HOSTNAME" ]]; then
  read -r -p "Public hostname (e.g. scanner.example.com): " CF_HOSTNAME
fi
# Strip scheme/path if the user pasted a full URL.
CF_HOSTNAME="${CF_HOSTNAME#http://}"; CF_HOSTNAME="${CF_HOSTNAME#https://}"; CF_HOSTNAME="${CF_HOSTNAME%%/*}"
[[ "$CF_HOSTNAME" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die "Hostname must be a full domain like scanner.example.com"

if [[ -z "$CF_TUNNEL_TOKEN" ]]; then
  read -r -s -p "Cloudflare Tunnel token: " CF_TUNNEL_TOKEN
  echo
fi
[[ -n "$CF_TUNNEL_TOKEN" ]] || die "Tunnel token is required (Zero Trust → Networks → Tunnels → your tunnel → token)."

# 3. Secret ------------------------------------------------------------------
if command -v python3 >/dev/null 2>&1; then
  SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
else
  SESSION_SECRET="$(openssl rand -hex 32)"
fi

# 4. Write .env --------------------------------------------------------------
umask 077
if [[ -f .env ]]; then
  backup=".env.backup.$(date +%Y%m%d%H%M%S)"
  cp .env "$backup"
  chmod 600 "$backup"
  info "Existing .env backed up to $backup"
fi
cat > .env <<EOF
ENVIRONMENT=production
SESSION_SECRET=${SESSION_SECRET}
COOKIE_SECURE=true
TRUSTED_HOSTS=${CF_HOSTNAME},localhost,127.0.0.1
ALLOWED_ORIGINS=https://${CF_HOSTNAME}
BIND_ADDRESS=127.0.0.1
HTTP_PORT=8080
TUNNEL_TOKEN=${CF_TUNNEL_TOKEN}
# Cloudflare free/pro plans cap request bodies at 100 MB.
MAX_UPLOAD_MB=90
MAX_PDF_MB=90
EOF
chmod 600 .env
info "Wrote production .env for ${CF_HOSTNAME}"

# 5. Start the stack ---------------------------------------------------------
bold "Building and starting containers (first build can take several minutes)…"
docker compose -f docker-compose.yml -f deployment/cloudflare/docker-compose.cloudflare.yml up -d --build

# 6. Wait for health ---------------------------------------------------------
bold "Waiting for the app to become healthy…"
healthy=0
for _ in $(seq 1 60); do
  api_id="$(docker compose ps -q api 2>/dev/null || true)"
  status="$(docker inspect -f '{{.State.Health.Status}}' "$api_id" 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then healthy=1; break; fi
  sleep 3
done
[[ "$healthy" == 1 ]] || die "App did not become healthy. Check: docker compose logs api worker nginx cloudflared"
info "Health OK"

# 7. Owner account -----------------------------------------------------------
bold "Create the owner account (password must be 12+ characters)"
if docker compose exec api python -m app.bootstrap --username owner; then
  info "Owner created"
else
  info "Owner was not created. If an owner already exists, sign in with it; otherwise check: docker compose logs api"
fi

# 8. Next steps --------------------------------------------------------------
cat <<NEXT

$(bold "Deployment complete.")
Open: https://${CF_HOSTNAME}

Remaining Cloudflare dashboard steps (if not done yet):
  1. Zero Trust → Networks → Tunnels → your tunnel → Public Hostname:
       ${CF_HOSTNAME}  →  http://nginx:8080
  2. Zero Trust → Access → Applications → Add → Self-hosted:
       hostname ${CF_HOSTNAME}, Allow policy = your email only.

Then sign in with the owner account you just created.
NEXT
