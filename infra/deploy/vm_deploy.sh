#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# ClearPort — build & run the whole stack directly on the GCE VM.
#
# Pulls the latest code, builds the backend + dashboard images locally on the
# VM (baking the public IP into the dashboard bundle), then (re)starts the
# four-container stack. No Artifact Registry, no GitHub Actions required.
#
# Usage (on the VM):
#   chmod +x vm_deploy.sh
#   IP=34.121.59.103 ./vm_deploy.sh
#
# Optional env overrides:
#   IP                 public external IP of the VM   (default: auto-detected)
#   REPO_URL           git clone URL                  (default: this repo)
#   SRC_DIR            where to clone/build            (default: ~/clearport-src)
#   GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION / models / POSTGRES_PASSWORD
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Config (override via env) ─────────────────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/akshayavarshinee/mission-sundar-pichai.git}"
SRC_DIR="${SRC_DIR:-$HOME/clearport-src}"
GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-clearport-498914}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
CLEARPORT_GEMINI_MODEL="${CLEARPORT_GEMINI_MODEL:-gemini-2.5-pro}"
CLEARPORT_JUDGE_MODEL="${CLEARPORT_JUDGE_MODEL:-gemini-2.5-pro}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-clearport}"
EASYPOST_API_KEY="${EASYPOST_API_KEY:-}"

# Auto-detect the VM's external IP from the metadata server if not provided.
if [[ -z "${IP:-}" ]]; then
  IP="$(curl -s -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip' || true)"
fi
if [[ -z "${IP}" ]]; then
  echo "✗ Could not determine the VM external IP. Re-run with: IP=<your.ip> ./vm_deploy.sh" >&2
  exit 1
fi

# Derive a free public hostname from the IP via sslip.io (no domain to buy):
#   34.134.197.83 → 34-134-197-83.sslip.io  (resolves straight back to the IP).
# Caddy uses it to fetch a real Let's Encrypt cert and front the whole app on
# HTTPS/443. Override with SITE_HOST=<your.domain> if you own one.
SITE_HOST="${SITE_HOST:-$(echo "${IP}" | tr '.' '-').sslip.io}"

# docker may need sudo depending on group membership.
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  DOCKER="sudo docker"
fi

echo "▶ IP             : ${IP}"
echo "▶ Public URL     : https://${SITE_HOST}"
echo "▶ Project / Loc  : ${GOOGLE_CLOUD_PROJECT} / ${GOOGLE_CLOUD_LOCATION}"
echo "▶ Source dir     : ${SRC_DIR}"
echo

# ── 1. Get the latest code ────────────────────────────────────────────────
if [[ -d "${SRC_DIR}/.git" ]]; then
  echo "▶ Updating existing checkout…"
  git -C "${SRC_DIR}" fetch --all --prune
  git -C "${SRC_DIR}" reset --hard origin/main
else
  echo "▶ Cloning ${REPO_URL}…"
  rm -rf "${SRC_DIR}"
  git clone "${REPO_URL}" "${SRC_DIR}"
fi

# The git repo root IS the clearport folder (contains Dockerfile + compose).
cd "${SRC_DIR}"
if [[ ! -f docker-compose.prod.yml ]]; then
  echo "✗ docker-compose.prod.yml not found in ${SRC_DIR}. Wrong repo layout?" >&2
  exit 1
fi

# ── 2. Tear down the current stack (keep volumes / DB data) ───────────────
echo "▶ Stopping existing containers…"
${DOCKER} compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
# Remove any stragglers by name, ignore if absent.
${DOCKER} rm -f clearport-api clearport-dashboard clearport-phoenix clearport-db 2>/dev/null || true

# ── 3. Build both images locally (bake the IP into the dashboard bundle) ──
echo "▶ Building backend image (clearport-api:local)…"
${DOCKER} build -t clearport-api:local -f Dockerfile .

echo "▶ Building dashboard image (clearport-dashboard:local) with API base https://${SITE_HOST}…"
${DOCKER} build \
  --build-arg NEXT_PUBLIC_API_BASE="https://${SITE_HOST}" \
  --build-arg NEXT_PUBLIC_PHOENIX_BASE="http://${IP}:6006" \
  -t clearport-dashboard:local \
  -f dashboard/Dockerfile dashboard

# ── 4. Write the .env the compose file consumes ───────────────────────────
echo "▶ Writing .env…"
cat > .env <<EOF
BACKEND_IMAGE=clearport-api:local
DASHBOARD_IMAGE=clearport-dashboard:local
SITE_HOST=${SITE_HOST}
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}
CLEARPORT_GEMINI_MODEL=${CLEARPORT_GEMINI_MODEL}
CLEARPORT_JUDGE_MODEL=${CLEARPORT_JUDGE_MODEL}
EASYPOST_API_KEY=${EASYPOST_API_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF

# ── 5. Bring the stack up ─────────────────────────────────────────────────
echo "▶ Starting the stack…"
${DOCKER} compose --env-file .env -f docker-compose.prod.yml up -d
${DOCKER} image prune -f >/dev/null 2>&1 || true

echo
echo "▶ Container status:"
${DOCKER} compose --env-file .env -f docker-compose.prod.yml ps

# ── 6. Quick verification ─────────────────────────────────────────────────
echo
echo "▶ Waiting for the backend to report healthy…"
for _ in $(seq 1 20); do
  if curl -fs http://localhost:8080/health >/dev/null 2>&1; then
    echo "  ✓ backend healthy"
    break
  fi
  sleep 3
done

echo "▶ Verifying the dashboard baked in the correct API base…"
if ${DOCKER} exec clearport-dashboard sh -c "grep -ro '${SITE_HOST}' .next | head -1" >/dev/null 2>&1; then
  echo "  ✓ dashboard points at https://${SITE_HOST}"
else
  echo "  ⚠ could not confirm baked host — hard-refresh the browser (Ctrl+Shift+R) and check the Network tab"
fi

cat <<DONE

✅ Done.
   Public URL : https://${SITE_HOST}          (HTTPS/443 — works behind firewalls)
   Backend    : https://${SITE_HOST}/health
   Phoenix    : http://${IP}:6006             (raw port; open from an unrestricted network)
   Raw ports  : http://${IP}:3000 (UI)  ·  http://${IP}:8080/health (API)

The first request to a brand-new host triggers a Let's Encrypt cert fetch (a few
seconds — needs GCP firewall tcp:80 + tcp:443 open). If the dashboard still says
"backend down", hard-refresh (Ctrl+Shift+R) to drop the old cached JS bundle. If
logs show a credentials error, the VM service account still needs the role:
roles/aiplatform.user.
DONE
