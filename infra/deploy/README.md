# Deploying ClearPort (both surfaces)

ClearPort hosts **two** surfaces, matching the locked decision:

1. **Web dashboard** — the cinematic, judge-usable UI (Next.js).
2. **Agent Builder app** — the ADK `root_agent` published in Vertex AI Agent
   Builder (link it from the dashboard header).

Both the backend and the dashboard deploy to **Cloud Run** from source (Cloud
Build builds the Dockerfiles in `../../Dockerfile` and `../../dashboard/Dockerfile`).

## 1. Prerequisites

```bash
gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com
```

## 2. Deploy the backend

```bash
PROJECT_ID=my-proj REGION=us-central1 ./deploy_backend.sh
# → prints the backend URL, e.g. https://clearport-api-xxxx.run.app
```

The backend boots **fully offline** (deterministic fallbacks for EasyPost,
Phoenix MCP, Vertex embeddings, Gemini, and Postgres), so it is demo-ready with
zero secrets. To progressively enable live services, set the corresponding env
vars / Secret Manager references (see `clearport/config.py`):

| Capability        | Enable with                                             |
| ----------------- | ------------------------------------------------------- |
| Gemini 3 brain    | `GOOGLE_API_KEY` (or Vertex creds) + `CLEARPORT_LLM_*`  |
| Phoenix tracing   | `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_API_KEY`         |
| Phoenix MCP       | `CLEARPORT_EPISODIC_BACKEND=phoenix`, MCP url/key       |
| Vertex embeddings | `CLEARPORT_EMBEDDINGS_BACKEND=vertex`                   |
| Postgres memory   | `CLEARPORT_VECTOR_BACKEND=pg` + Cloud SQL connection    |
| EasyPost (test)   | `EASYPOST_API_KEY` (test key)                           |

## 3. Deploy the dashboard

```bash
PROJECT_ID=my-proj REGION=us-central1 \
NEXT_PUBLIC_API_BASE=https://clearport-api-xxxx.run.app \
NEXT_PUBLIC_PHOENIX_BASE=https://app.phoenix.arize.com \
./deploy_dashboard.sh
```

## 4. Publish the Agent Builder app

Deploy the ADK agent (`clearport/agents/adk_app.py:root_agent`) to Vertex AI
Agent Builder, then set `NEXT_PUBLIC_AGENT_BUILDER_URL` on the dashboard service
so the header deep-links to it.

## 5. (Optional) Cloud SQL + pgvector

Provision Cloud SQL for PostgreSQL, run `../cloudsql/001_init.sql`, then set
`CLEARPORT_VECTOR_BACKEND=pg` and the connection settings. The in-memory store
is the default and needs nothing.
