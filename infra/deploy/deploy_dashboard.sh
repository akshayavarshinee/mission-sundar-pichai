#!/usr/bin/env bash
# Deploy the ClearPort dashboard (Next.js) to Cloud Run.
#
# Prereqs: gcloud CLI authenticated; PROJECT_ID set; the backend already
# deployed (so you know its public URL).
#
# Usage:
#   PROJECT_ID=my-proj REGION=us-central1 \
#   NEXT_PUBLIC_API_BASE=https://clearport-api-xxxx.run.app \
#   NEXT_PUBLIC_PHOENIX_BASE=https://app.phoenix.arize.com \
#   ./deploy_dashboard.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${DASHBOARD_SERVICE:-clearport-dashboard}"
API_BASE="${NEXT_PUBLIC_API_BASE:?set NEXT_PUBLIC_API_BASE to the backend URL}"
PHOENIX_BASE="${NEXT_PUBLIC_PHOENIX_BASE:-https://app.phoenix.arize.com}"
DASH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../dashboard" && pwd)"

echo "▶ Building & deploying ${SERVICE} from ${DASH_DIR}"
echo "  API base: ${API_BASE}"

gcloud run deploy "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --source "${DASH_DIR}" \
  --allow-unauthenticated \
  --cpu 1 --memory 512Mi \
  --min-instances 1 \
  --port 3000 \
  --set-env-vars "NEXT_PUBLIC_API_BASE=${API_BASE},NEXT_PUBLIC_PHOENIX_BASE=${PHOENIX_BASE}"

URL="$(gcloud run services describe "${SERVICE}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.url)')"

echo "✅ Dashboard live at: ${URL}"
