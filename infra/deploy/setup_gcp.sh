#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# ClearPort — one-time GCP provisioning for the single-VM Docker deployment.
#
# Creates everything the push-to-main pipeline needs:
#   • Enables required APIs
#   • An Artifact Registry repo for the backend/dashboard images
#   • A reserved static external IP + an e2-medium VM with Docker pre-installed
#   • Firewall rules (app ports + IAP SSH range)
#   • A deploy service account + Workload Identity Federation for GitHub Actions
#     (no long-lived JSON keys)
#
# Run it ONCE from a machine with the gcloud CLI authenticated as an owner:
#
#   PROJECT_ID=my-proj GITHUB_REPO=my-org/my-repo ./setup_gcp.sh
#
# When it finishes it prints the GitHub secrets/variables to configure.
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Inputs ────────────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID to your GCP project id}"
GITHUB_REPO="${GITHUB_REPO:?set GITHUB_REPO as owner/repo (e.g. acme/clearport)}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE="${INSTANCE:-clearport-vm}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-medium}"          # 2 vCPU / 4 GB — fits all 4 containers
DISK_SIZE="${DISK_SIZE:-30GB}"
AR_REPO="${AR_REPO:-clearport}"
SA_NAME="${SA_NAME:-clearport-deployer}"
POOL_ID="${POOL_ID:-github-pool}"
PROVIDER_ID="${PROVIDER_ID:-github-provider}"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IP_NAME="${INSTANCE}-ip"

echo "▶ Project        : ${PROJECT_ID}"
echo "▶ Region / Zone  : ${REGION} / ${ZONE}"
echo "▶ GitHub repo    : ${GITHUB_REPO}"
echo

gcloud config set project "${PROJECT_ID}" >/dev/null

# ── 1. APIs ───────────────────────────────────────────────────────────────
echo "▶ Enabling APIs…"
gcloud services enable \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  iap.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

# ── 2. Artifact Registry ──────────────────────────────────────────────────
echo "▶ Artifact Registry repo '${AR_REPO}'…"
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker --location="${REGION}" \
  --description="ClearPort container images" 2>/dev/null \
  || echo "  (already exists)"

# ── 3. Static IP ──────────────────────────────────────────────────────────
echo "▶ Reserving static external IP '${IP_NAME}'…"
gcloud compute addresses create "${IP_NAME}" --region="${REGION}" 2>/dev/null \
  || echo "  (already exists)"
STATIC_IP="$(gcloud compute addresses describe "${IP_NAME}" --region="${REGION}" --format='value(address)')"
echo "  → ${STATIC_IP}"

# ── 4. Firewall ───────────────────────────────────────────────────────────
echo "▶ Firewall rules…"
# Public app ports: backend 8080, dashboard 3000, Phoenix 6006.
gcloud compute firewall-rules create clearport-app \
  --direction=INGRESS --action=ALLOW \
  --rules=tcp:8080,tcp:3000,tcp:6006 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clearport 2>/dev/null || echo "  (clearport-app exists)"
# SSH only from Google IAP range (CI tunnels through IAP — no public :22).
gcloud compute firewall-rules create clearport-iap-ssh \
  --direction=INGRESS --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags=clearport 2>/dev/null || echo "  (clearport-iap-ssh exists)"

# ── 5. VM (Docker pre-installed via startup script, OS Login on) ──────────
echo "▶ Creating VM '${INSTANCE}'…"
STARTUP="$(cat <<'EOF'
#!/usr/bin/env bash
set -e
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi
EOF
)"

gcloud compute instances create "${INSTANCE}" \
  --zone="${ZONE}" \
  --machine-type="${MACHINE_TYPE}" \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size="${DISK_SIZE}" \
  --address="${STATIC_IP}" \
  --tags=clearport \
  --metadata=enable-oslogin=TRUE \
  --metadata-from-file=startup-script=<(echo "${STARTUP}") 2>/dev/null \
  || echo "  (instance already exists)"

# ── 6. Deploy service account + roles ─────────────────────────────────────
echo "▶ Service account '${SA_EMAIL}'…"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="ClearPort GitHub Actions deployer" 2>/dev/null \
  || echo "  (already exists)"

for ROLE in \
  roles/artifactregistry.writer \
  roles/compute.instanceAdmin.v1 \
  roles/compute.osAdminLogin \
  roles/iap.tunnelResourceAccessor \
  roles/iam.serviceAccountUser ; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}" \
    --condition=None >/dev/null
done

# ── 7. Workload Identity Federation for GitHub Actions ────────────────────
echo "▶ Workload Identity Federation…"
gcloud iam workload-identity-pools create "${POOL_ID}" \
  --location=global --display-name="GitHub Actions pool" 2>/dev/null \
  || echo "  (pool exists)"

gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
  --location=global --workload-identity-pool="${POOL_ID}" \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='${GITHUB_REPO}'" 2>/dev/null \
  || echo "  (provider exists)"

# Only the configured repo may impersonate the deployer SA.
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}" \
  >/dev/null

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

# ── Done — print the GitHub configuration ─────────────────────────────────
cat <<SUMMARY

✅ Provisioning complete.

Add these to your GitHub repo (Settings → Secrets and variables → Actions):

  Repository VARIABLES:
    GCP_PROJECT_ID        = ${PROJECT_ID}
    GCP_REGION            = ${REGION}
    GCP_ZONE              = ${ZONE}
    GCE_INSTANCE          = ${INSTANCE}
    AR_REPO               = ${AR_REPO}
    WIF_SERVICE_ACCOUNT   = ${SA_EMAIL}
    STATIC_IP             = ${STATIC_IP}

  Repository SECRETS:
    WIF_PROVIDER          = ${WIF_PROVIDER}
    GOOGLE_API_KEY        = <your Gemini AI Studio key>
    # optional:
    EASYPOST_API_KEY      = <EasyPost TEST key, EZTK…>

Then push to main — the deploy workflow builds, pushes, and rolls out the stack.

Surfaces (after first deploy):
    Dashboard : http://${STATIC_IP}:3000
    Backend   : http://${STATIC_IP}:8080/health
    Phoenix   : http://${STATIC_IP}:6006
SUMMARY
