#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# ClearPort — backend-only stack for Vercel frontend split deployment.
#
# Builds and runs phoenix + db + backend (+ optional HTTPS Caddy) on the VM.
# Point Vercel BACKEND_UPSTREAM at https://${SITE_HOST} or http://${IP}:8080.
#
# Usage (on the VM):
#   chmod +x vm_deploy_backend_only.sh
#   IP=34.121.59.103 ./vm_deploy_backend_only.sh
#
# With HTTPS (recommended for Vercel):
#   IP=34.121.59.103 ENABLE_HTTPS=1 ./vm_deploy_backend_only.sh
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/akshayavarshinee/mission-sundar-pichai.git}"
SRC_DIR="${SRC_DIR:-$HOME/clearport-src}"
GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-clearport-498914}"
GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
CLEARPORT_GEMINI_MODEL="${CLEARPORT_GEMINI_MODEL:-gemini-2.5-pro}"
CLEARPORT_JUDGE_MODEL="${CLEARPORT_JUDGE_MODEL:-gemini-2.5-pro}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-clearport}"
EASYPOST_API_KEY="${EASYPOST_API_KEY:-}"
ENABLE_HTTPS="${ENABLE_HTTPS:-0}"

if [[ -z "${IP:-}" ]]; then
  IP="$(curl -s -H 'Metadata-Flavor: Google' \
    'http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip' || true)"
fi
if [[ -z "${IP}" ]]; then
  echo "✗ Could not determine VM external IP. Re-run with: IP=<your.ip> ./vm_deploy_backend_only.sh" >&2
  exit 1
fi

SITE_HOST="${SITE_HOST:-$(echo "${IP}" | tr '.' '-').sslip.io}"

DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  DOCKER="sudo docker"
fi

echo "▶ Mode           : backend-only (frontend on Vercel)"
echo "▶ IP             : ${IP}"
echo "▶ SITE_HOST      : ${SITE_HOST}"
echo "▶ HTTPS (Caddy)  : ${ENABLE_HTTPS}"
echo

if [[ -d "${SRC_DIR}/.git" ]]; then
  git -C "${SRC_DIR}" fetch --all --prune
  git -C "${SRC_DIR}" reset --hard origin/main
else
  rm -rf "${SRC_DIR}"
  git clone "${REPO_URL}" "${SRC_DIR}"
fi

cd "${SRC_DIR}"

${DOCKER} compose -f docker-compose.backend.yml down --remove-orphans 2>/dev/null || true
${DOCKER} rm -f clearport-api clearport-phoenix clearport-db clearport-caddy-api 2>/dev/null || true

echo "▶ Building backend image…"
${DOCKER} build -t clearport-api:local -f Dockerfile .

cat > .env.backend <<EOF
BACKEND_IMAGE=clearport-api:local
SITE_HOST=${SITE_HOST}
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION}
CLEARPORT_GEMINI_MODEL=${CLEARPORT_GEMINI_MODEL}
CLEARPORT_JUDGE_MODEL=${CLEARPORT_JUDGE_MODEL}
EASYPOST_API_KEY=${EASYPOST_API_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF

COMPOSE_PROFILES=""
if [[ "${ENABLE_HTTPS}" == "1" ]]; then
  COMPOSE_PROFILES="--profile https"
fi

echo "▶ Starting backend stack…"
${DOCKER} compose --env-file .env.backend -f docker-compose.backend.yml ${COMPOSE_PROFILES} up -d

for _ in $(seq 1 20); do
  if curl -fs "http://localhost:8080/health" >/dev/null 2>&1; then
    echo "  ✓ backend healthy"
    break
  fi
  sleep 3
done

if [[ "${ENABLE_HTTPS}" == "1" ]]; then
  BACKEND_URL="https://${SITE_HOST}"
else
  BACKEND_URL="http://${IP}:8080"
fi

cat <<DONE

✅ Backend stack is up.

Set these in Vercel → Project → Environment Variables:

  BACKEND_UPSTREAM=${BACKEND_URL}
  NEXT_PUBLIC_API_BASE=
  NEXT_PUBLIC_PHOENIX_BASE=http://${IP}:6006

Verify:
  curl -fs ${BACKEND_URL}/health
  open http://${IP}:6006

Deploy frontend:
  cd dashboard && vercel --prod
  (or connect the repo in Vercel with Root Directory = dashboard)

DONE
