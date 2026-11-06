#!/usr/bin/env bash
# Activate Cloudflare Worker proxy mode for an already-running OmniFix app.
#
# Run this on any machine with Node 22+ and Wrangler access to your Cloudflare
# account (npx wrangler login, or CLOUDFLARE_API_TOKEN set):
#
#   bash scripts/activate-worker-proxy.sh
#
# It will:
#   1. Ask for the HTTPS origin where OmniFix is already running.
#   2. Optionally ask for a Cloudflare Access service token (id + secret).
#   3. Store them as Worker secrets via wrangler (nothing is written to Git).
#   4. Deploy the Worker and verify the proxy responds.
#
# The real app must already be running (Docker + Tunnel). This does not deploy
# the Python backend to Workers; it only points the Worker at your origin.
set -euo pipefail
cd "$(dirname "$0")/.."

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die() { printf '\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

bold "OmniFix — activate Cloudflare Worker proxy mode"

# 1. Prerequisites -----------------------------------------------------------
command -v node >/dev/null 2>&1 || die "Node.js is required (22+). Install it from https://nodejs.org"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$NODE_MAJOR" -ge 22 ]] || die "Wrangler requires Node 22+. Found $(node -v)."
command -v curl >/dev/null 2>&1 || die "curl is required for the verification step."

WRANGLER=(npx -y wrangler@4.158.0)

# 2. Origin ------------------------------------------------------------------
ORIGIN="${OMNIFIX_ORIGIN:-}"
if [[ -z "$ORIGIN" ]]; then
  read -r -p "HTTPS origin where OmniFix is running (e.g. https://scanner.example.com): " ORIGIN
fi
ORIGIN="${ORIGIN%/}"
[[ "$ORIGIN" =~ ^https://[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die "Origin must be https://hostname with no path, e.g. https://scanner.example.com"
info "Origin: $ORIGIN"

# 3. Optional Access service token -------------------------------------------
USE_ACCESS="${USE_ACCESS:-}"
if [[ -z "$USE_ACCESS" ]]; then
  read -r -p "Is that origin protected by Cloudflare Access? [y/N]: " USE_ACCESS
fi
ACCESS_ID=""
ACCESS_SECRET=""
if [[ "$USE_ACCESS" =~ ^[Yy] ]]; then
  ACCESS_ID="${CF_ACCESS_CLIENT_ID:-}"
  ACCESS_SECRET="${CF_ACCESS_CLIENT_SECRET:-}"
  if [[ -z "$ACCESS_ID" ]]; then
    read -r -p "Access service token Client ID: " ACCESS_ID
  fi
  if [[ -z "$ACCESS_SECRET" ]]; then
    read -r -s -p "Access service token Client Secret: " ACCESS_SECRET
    echo
  fi
  [[ -n "$ACCESS_ID" && -n "$ACCESS_SECRET" ]] || die "Both Access Client ID and Client Secret are required."
  bold "Remember: protect the Worker itself with Cloudflare Access too, or it becomes a public bypass."
fi

# 4. Auth check --------------------------------------------------------------
bold "Checking Wrangler authentication…"
if ! "${WRANGLER[@]}" whoami >/dev/null 2>&1; then
  die "Wrangler is not authenticated. Run: npx wrangler login   (or set CLOUDFLARE_API_TOKEN)"
fi
info "Authenticated"

# 5. Store secrets -----------------------------------------------------------
bold "Storing Worker secrets (not committed to Git)…"
printf '%s' "$ORIGIN" | "${WRANGLER[@]}" secret put OMNIFIX_ORIGIN --name pdf
if [[ -n "$ACCESS_ID" ]]; then
  printf '%s' "$ACCESS_ID" | "${WRANGLER[@]}" secret put CF_ACCESS_CLIENT_ID --name pdf
  printf '%s' "$ACCESS_SECRET" | "${WRANGLER[@]}" secret put CF_ACCESS_CLIENT_SECRET --name pdf
fi
info "Secrets stored"

# 6. Deploy ------------------------------------------------------------------
bold "Deploying the Worker…"
"${WRANGLER[@]}" deploy

# 7. Verify ------------------------------------------------------------------
bold "Verifying the proxy…"
WORKER_URL="$("${WRANGLER[@]}" deployments status 2>/dev/null | grep -Eo 'https://[a-z0-9.-]+\.workers\.dev' | head -1 || true)"
if [[ -z "$WORKER_URL" ]]; then
  read -r -p "Enter your Worker URL (https://pdf.<subdomain>.workers.dev): " WORKER_URL
fi
if [[ -n "$WORKER_URL" ]]; then
  CODE="$(curl -s -o /tmp/omnifix-proxy-check.json -w '%{http_code}' "${WORKER_URL%/}/api/health" || true)"
  if [[ "$CODE" == "200" ]]; then
    info "Proxy OK: ${WORKER_URL} -> origin health 200"
  elif [[ "$CODE" == "502" ]]; then
    info "Worker deployed, but origin unreachable (502). Check the app/Tunnel and OMNIFIX_ORIGIN."
  elif [[ "$CODE" == "501" ]]; then
    info "Worker still in guard mode (501). The OMNIFIX_ORIGIN secret may not have applied yet; redeploy."
  else
    info "Worker responded with HTTP ${CODE}. If Access protects the origin/Worker, this may be an Access redirect."
  fi
fi

cat <<NEXT

$(bold "Done.")
Open your Worker URL in a browser. You should see the OmniFix login (or Cloudflare Access first).
If you use Access service auth, make sure the Worker hostname is also protected by Access.
NEXT
