#!/usr/bin/env bash
# Deploy the ClearPort backend (FastAPI + agent loop) to Cloud Run.
#
# Prereqs: gcloud CLI authenticated; PROJECT_ID set; billing + Cloud Run,
# Artifact Registry, and Cloud Build APIs enabled.
#
# Usage:
#   PROJECT_ID=my-proj REGION=us-central1 ./deploy_backend.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE="${BACKEND_SERVICE:-clearport-api}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "▶ Building & deploying ${SERVICE} from ${REPO_DIR}"

gcloud run deploy "${SERVICE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --source "${REPO_DIR}" \
  --allow-unauthenticated \
  --cpu 1 --memory 1Gi \
  --min-instances 1 \
  --timeout 600 \
  --set-env-vars "CLEARPORT_ENV=cloud" \
  --port 8080

URL="$(gcloud run services describe "${SERVICE}" \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --format='value(status.url)')"

echo "✅ Backend live at: ${URL}"
echo "   Set NEXT_PUBLIC_API_BASE=${URL} before deploying the dashboard."
