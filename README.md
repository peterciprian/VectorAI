# VectoryAI

AI-assisted vectorization of Hungarian urban planning maps.

VectoryAI is a modular monorepo with independently runnable services. The initial scaffold provides a Next.js-ready web application, a FastAPI API, a Celery worker, shared contracts, and local PostgreSQL/PostGIS and Redis infrastructure.

## Repository layout

```text
apps/
  api/       FastAPI gateway
  worker/    Celery processing worker
  web/       Next.js frontend shell
packages/
  contracts/ Shared API and job contracts
infrastructure/
  postgres/  PostgreSQL initialization
  storage/   Local artifact directory
architecture.md
backlog.md
user_stories.md
vision.md
compose.yaml
compose.production.yaml Legacy VM deployment alternative
deploy/                 Render deployment runbook and legacy VM files
render.yaml             Render Blueprint for the free backend services
```

## Prerequisites

- Docker Desktop with Compose
- Node.js 20+ and npm (for the web app)
- Python 3.11+ and a virtual environment (for API/worker development outside Docker)

## Start local infrastructure

```powershell
docker compose up --build
```

Services:

- Web: http://localhost:3000
- API health: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- PostgreSQL/PostGIS: localhost:5432
- Redis: localhost:6379

## Deploy the backend on Render

The UI is deployed separately to GitHub Pages. The recommended free backend setup uses Render:

```text
Render Web Service -> FastAPI API
Render Postgres -> PostGIS database
Render Key Value -> Redis-compatible queue
Local or paid worker -> Celery processing
```

Render's free plan does not currently include an always-on background worker. Use the local worker for development, or add a paid Render Background Worker when continuous processing is needed. Free Render Postgres expires after 30 days and free Key Value is in-memory, so this setup is for testing and early prototypes.

Use the full [Render deployment runbook](deploy/DEPLOYMENT.md). The short version is:

```text
1. Create a Render Blueprint from render.yaml.
2. Keep API, Postgres, and Key Value in the same region.
3. Enable PostGIS with CREATE EXTENSION postgis.
4. Test /health on the generated Render API URL.
5. Run the Celery worker locally until a paid worker is available.
```

The Oracle VM deployment files remain available as a legacy alternative in `compose.production.yaml` and `deploy/`.

## Deploy the UI to GitHub Pages

The `Deploy UI to GitHub Pages` workflow builds `apps/web` as a static Next.js export and publishes it on every push to `main` that changes the UI. The project site is available at:

```text
https://peterciprian.github.io/VectorAI/
```

In the GitHub repository settings, set **Pages > Build and deployment > Source** to **GitHub Actions**. The workflow uses the repository name as the Next.js base path for Pages, while local development continues to run from `/`.

The current API and worker are intentionally minimal foundations. Processing modules, authentication, uploads, and OpenLayers workflows are introduced incrementally according to `backlog.md`.

## Run services directly

API:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Worker:

```powershell
cd apps/worker
pip install -r requirements.txt
celery -A app.celery_app.celery_app worker --loglevel=INFO
```

Web:

```powershell
cd apps/web
npm install
npm run dev
```

## Configuration

Copy `.env.example` to `.env` for local overrides. Do not commit `.env` files or generated raster/vector artifacts.

## Development principles

- `apps/web` talks to `apps/api`; it does not access databases directly.
- `apps/api` owns HTTP, project state, uploads, job submission, and SSE.
- `apps/worker` owns asynchronous processing.
- `packages/contracts` is the source of truth for cross-service payloads.
- Heavy GIS dependencies stay in worker-focused packages and images.

## Documentation

See `vision.md`, `user_stories.md`, `architecture.md`, and `backlog.md` for the product and technical direction.
