# Deploying ClearPort to GCP (single VM, push-to-main)

ClearPort runs as **four containers on one Always-On GCE VM**, deployed
automatically on every push to `main`:

| Container   | Image                                       | Port | Purpose                          |
| ----------- | ------------------------------------------- | ---- | -------------------------------- |
| `backend`   | Artifact Registry (`clearport-api`)         | 8080 | FastAPI + agent loop             |
| `dashboard` | Artifact Registry (`clearport-dashboard`)   | 3000 | Next.js UI                       |
| `phoenix`   | `arizephoenix/phoenix` (self-hosted)        | 6006 | Tracing / evals — **no API key** |
| `db`        | `pgvector/pgvector:pg16`                     | 5432 | Memory tiers ① law / ③ lessons   |

> Self-hosted Phoenix means **no Arize account / API key** is required — the
> backend exports traces over OTLP/HTTP to `http://phoenix:6006` on the same
> internal network.

## 1. One-time provisioning

From a machine with the `gcloud` CLI authenticated as a project owner:

```bash
cd infra/deploy
PROJECT_ID=my-proj GITHUB_REPO=my-org/clearport ./setup_gcp.sh
```

This enables APIs, creates an Artifact Registry repo, a reserved static IP, an
`e2-medium` VM with Docker, firewall rules, a deploy service account, and
**Workload Identity Federation** (so CI needs no long-lived JSON key). It prints
the exact GitHub values to configure next.

## 2. Configure GitHub (Settings → Secrets and variables → Actions)

**Variables**

| Name                  | Example                                              |
| --------------------- | ---------------------------------------------------- |
| `GCP_PROJECT_ID`      | `my-proj`                                             |
| `GCP_REGION`          | `us-central1`                                         |
| `GCP_ZONE`            | `us-central1-a`                                       |
| `GCE_INSTANCE`        | `clearport-vm`                                        |
| `AR_REPO`             | `clearport`                                           |
| `STATIC_IP`           | `34.x.x.x` (printed by the setup script)             |
| `WIF_SERVICE_ACCOUNT` | `clearport-deployer@my-proj.iam.gserviceaccount.com` |

**Secrets**

| Name               | Value                                                  |
| ------------------ | ------------------------------------------------------ |
| `WIF_PROVIDER`     | `projects/NNN/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GOOGLE_API_KEY`   | Gemini AI Studio key (the live brain)                  |
| `EASYPOST_API_KEY` | *(optional)* EasyPost **test** key (`EZTK…`)           |
| `POSTGRES_PASSWORD`| *(optional)* DB password; defaults to `clearport`      |

## 3. Deploy

Push to `main`. The pipeline runs:

1. **`ci`** — lint + unit tests (`.github/workflows/ci.yml`).
2. **`deploy`** — only after CI passes (`.github/workflows/deploy.yml`):
   builds both images, pushes them to Artifact Registry, copies
   `docker-compose.prod.yml` to the VM, writes `.env` from the secrets, then
   `docker compose pull && up -d` over an IAP SSH tunnel.

You can also trigger it manually from the **Actions** tab (`workflow_dispatch`).

After the first deploy:

| Surface   | URL                              |
| --------- | -------------------------------- |
| Dashboard | `http://<STATIC_IP>:3000`        |
| Backend   | `http://<STATIC_IP>:8080/health` |
| Phoenix   | `http://<STATIC_IP>:6006`        |

## Cost (within the $300 free credits)

A single `e2-medium` (2 vCPU / 4 GB) + 30 GB disk + static IP runs **~$25/mo**,
so the credits comfortably cover ~10–12 months. To pause billing, stop the VM:

```bash
gcloud compute instances stop clearport-vm --zone us-central1-a
```

## Notes

- The backend boots with deterministic offline fallbacks, so it stays up even
  before `GOOGLE_API_KEY` is set — add the key and re-run the workflow to use
  the live Gemini brain.
- `NEXT_PUBLIC_API_BASE` / `NEXT_PUBLIC_PHOENIX_BASE` are baked into the
  dashboard image at build time from `STATIC_IP`, which is why a reserved
  (non-ephemeral) IP is used.
- HTTP-only on raw ports is fine for the demo. For HTTPS + clean URLs later, put
  a reverse proxy (e.g. Caddy) in front and point a domain at the static IP.
- The legacy Cloud Run scripts (`deploy_backend.sh`, `deploy_dashboard.sh`)
  remain in this folder as an alternative path; the VM flow above is the
  supported default.
