# VectoryAI Render Deployment Runbook

This runbook deploys the VectoryAI backend to Render. The frontend remains on GitHub Pages.

## Important free-tier limitation

Render's current free services include web services, Render Postgres, and Render Key Value. A continuously running background worker is not available on the free plan.

The completely free setup can run:

```text
GitHub Pages -> static Next.js UI
Render -> FastAPI API
Render -> PostgreSQL + PostGIS
Render -> Key Value (Redis-compatible queue)
Your computer -> Celery worker, while it is online
```

For continuous asynchronous processing, the worker requires a paid Render background worker, another always-on worker host, or a local worker during development. Do not treat the free Render setup as a complete production processing environment until a worker is available.

## What is included in this repository

- `render.yaml`: Render Blueprint for the free API, Postgres, and Key Value services.
- `apps/api/Dockerfile`: API image configured to use Render's injected `PORT`.
- `apps/worker/Dockerfile`: Celery image for a paid Render worker or another host.
- `compose.production.yaml`: legacy VM deployment; it is not needed for Render.

## 1. Prepare the repository

The Blueprint is read from the repository root. Before using it, make sure the Render deployment configuration is committed and pushed to GitHub. Render will not see uncommitted local files.

The Blueprint creates services in the Frankfurt region. Keep the API, Postgres, and Key Value in the same region for private networking.

## 2. Create the Render project

1. Open [Render Dashboard](https://dashboard.render.com/).
2. Sign in with GitHub.
3. Select **New > Blueprint**.
4. Select the `peterciprian/VectorAI` repository.
5. Select the `main` branch.
6. Confirm that Render detected `render.yaml`.
7. Review the resources before creating them.
8. Create the Blueprint.

Render free resources are intended for testing or hobby use. Free Postgres is limited to 1 GB and expires 30 days after creation. Free Key Value is in-memory and loses its data after a restart. The free API service can spin down after inactivity and may take about a minute to wake up.

## 3. Confirm the services

The Blueprint should create:

```text
vectoryai-api       Web Service, free plan
vectoryai-postgres  Render Postgres, free plan, 1 GB
vectoryai-keyvalue  Render Key Value, free plan, internal access only
```

Open the API service and copy its public URL, for example:

```text
https://vectoryai-api.onrender.com
```

The API health check is:

```text
https://vectoryai-api.onrender.com/health
```

The API receives these variables from the Blueprint:

```text
DATABASE_URL
REDIS_URL
STORAGE_ROOT
CORS_ORIGINS
```

The API and datastores must stay in the same Render region. The Blueprint uses internal service connection references, so credentials do not need to be copied manually.

## 4. Enable PostGIS

Render Postgres supports PostGIS, but it must be enabled in the database.

Open the Postgres service in Render and use its provided external `PSQL Command`, or connect with `psql` from your computer. Run:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
```

Verify it:

```sql
SELECT PostGIS_Version();
```

Do not put the external database URL in the frontend or in Git. Use it only for administrative access. Render services in the same region use the internal connection string supplied to `DATABASE_URL`.

## 5. Configure GitHub Pages to know the API URL

The current UI is a static landing page and does not yet call the API. When API calls are introduced, update the GitHub Pages workflow with the Render API URL:

```yaml
- name: Build static export
  run: npm run export
  working-directory: apps/web
  env:
    GITHUB_ACTIONS: 'true'
    NEXT_PUBLIC_API_URL: https://vectoryai-api.onrender.com
```

The API's `CORS_ORIGINS` must remain:

```text
https://peterciprian.github.io/VectorAI
```

## 6. Validate the API

From PowerShell:

```powershell
curl.exe https://vectoryai-api.onrender.com/health
curl.exe -I https://vectoryai-api.onrender.com/docs
```

Expected health response:

```json
{
  "status": "ok",
  "service": "api",
  "timestamp": "..."
}
```

The first request after inactivity may be slow because the free web service is waking up.

## 7. Run the Celery worker locally for free

Until a paid worker is available, run the worker on your development computer. It must reach Render Key Value and Render Postgres.

Because Render datastores are private by default, obtain their external connection URLs from the Render Dashboard and enable external access only for your development IP. Treat those URLs as secrets.

On the development computer:

```powershell
cd apps/worker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:REDIS_URL = '<Render Key Value external URL>'
$env:DATABASE_URL = '<Render Postgres external URL>'
$env:STORAGE_ROOT = '.\storage\projects'
celery -A app.celery_app.celery_app worker --loglevel=INFO --concurrency=1
```

This is suitable for development only. Jobs cannot run while the computer or worker process is offline. Large artifacts should not be stored in Render service filesystems because free services have ephemeral filesystems.

## 8. Add a paid Render worker later

When continuous processing is required, create a Render **Background Worker** from the same repository:

```text
Service type: Background Worker
Runtime: Docker
Root directory: apps/worker
Dockerfile: Dockerfile
Docker context: apps/worker
Start command:
  celery -A app.celery_app.celery_app worker --loglevel=INFO --concurrency=1
```

Set these environment variables using the internal Render connections:

```text
REDIS_URL=<internal Key Value connection string>
DATABASE_URL=<internal Postgres connection string>
STORAGE_ROOT=/tmp/project_storage
```

The commented worker definition in `render.yaml` shows the intended service configuration. Uncomment it only after choosing a paid worker plan. Keep worker concurrency at 1 until real resource measurements justify increasing it.

## 9. Storage warning

The current API uses `STORAGE_ROOT` for future uploaded files and artifacts. Render free services have ephemeral filesystems, so files written there can disappear after redeploys, restarts, or spin-down.

Before implementing real uploads, add durable object storage such as Cloudflare R2, Amazon S3, or another S3-compatible store.

Store project metadata, GCPs, legend classes, and vector records in Postgres. Store PDFs, raster masters, tiles, COG GeoTIFFs, GeoJSON files, and Shapefile archives in object storage.

## 10. Free-tier limits to monitor

- Free web services spin down after 15 minutes without inbound traffic.
- Free web services have 750 included instance hours per workspace per month.
- Free web service files are not persistent.
- Free Render Postgres has 1 GB of storage.
- Free Render Postgres expires 30 days after creation and has no backups.
- Only one free Postgres instance is available per workspace.
- Free Key Value is in-memory and loses data on restart.
- Only one free Key Value instance is available per workspace.
- Free resources are for testing, hobby projects, and previews rather than production.

## 11. Troubleshooting

### API is sleeping or slow

Wait for the free web service to wake up. Check the Render service logs and health endpoint. This is expected behavior on the free plan.

### API cannot connect to Postgres or Key Value

Check that all services are in the same Render region and that the Blueprint created internal connection references. Do not use a localhost URL in Render environment variables.

### PostGIS is unavailable

Connect to Render Postgres and run:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();
```

### Celery jobs remain pending

The free setup has no always-on Render worker. Start the local worker from section 7, or add the paid worker from section 8. Check that the worker uses the same Redis URL as the API.

### Render Key Value lost queue state

This is expected after a free Key Value restart. Redis/Valkey is queue state, not durable project data. Retry or recreate affected jobs after the worker reconnects.

## 12. Deployment checklist

```text
[ ] Render account connected to GitHub
[ ] render.yaml detected from main
[ ] API, Postgres, and Key Value created in one region
[ ] API public URL recorded
[ ] /health responds
[ ] PostGIS extension enabled
[ ] GitHub Pages origin present in CORS_ORIGINS
[ ] GitHub Pages workflow configured with API URL when API calls are added
[ ] External datastore access restricted to development IP if local worker is used
[ ] Local Celery worker tested, or paid worker enabled
[ ] Object storage selected before implementing uploads
[ ] Free-tier expiry and storage limits understood
```

## Official Render documentation

- [Deploy for Free](https://render.com/docs/free.md)
- [Blueprint YAML Reference](https://render.com/docs/blueprint-spec.md)
- [Deploy a FastAPI App](https://render.com/docs/deploy-fastapi.md)
- [Background Workers](https://render.com/docs/background-workers.md)
- [Render Key Value](https://render.com/docs/key-value.md)
- [Create and Connect to Render Postgres](https://render.com/docs/postgresql-creating-connecting.md)
- [Supported Postgres Extensions](https://render.com/docs/postgresql-extensions.md)
