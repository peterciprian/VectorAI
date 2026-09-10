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
compose.production.yaml
deploy/                 Oracle VM and Caddy deployment files
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

## Deploy the backend on an Oracle Always Free VM

The UI is deployed separately to GitHub Pages. `compose.production.yaml` runs the backend stack on a Linux VM:

```text
Caddy -> FastAPI API -> Redis / Celery worker / PostgreSQL + PostGIS
```

The production Compose file does not run the Next.js web service. It expects an ARM64 Oracle Ampere A1 VM, a DNS record pointing `API_DOMAIN` to the VM, and inbound TCP ports `80`, `443`, and `22` allowed by the Oracle security list. PostgreSQL, Redis, and the API are private to the Compose network.

On the VM:

```bash
git clone https://github.com/peterciprian/VectorAI.git
cd VectorAI
cp deploy/.env.production.example .env.production
# Edit .env.production with the real API hostname, email, password, and CORS origin.
docker compose --env-file .env.production -f compose.production.yaml up -d --build
docker compose --env-file .env.production -f compose.production.yaml ps
```

For a new Ubuntu ARM64 VM, `deploy/bootstrap-ubuntu-arm64.sh` installs Docker Engine and the Compose plugin. Run it once, log out and back in, then run the Compose commands above. Keep `.env.production` private and back up the named `postgres_data` and `project_storage` volumes before using real project files.

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
