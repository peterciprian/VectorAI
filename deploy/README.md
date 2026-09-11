# Render Deployment

The recommended free deployment is:

```text
GitHub Pages -> Next.js UI
Render -> FastAPI API
Render -> Postgres + PostGIS
Render -> Key Value / Redis-compatible queue
Local computer -> Celery worker during development
```

Render's free plan does not currently include an always-on background worker. Continuous Celery processing requires a paid Render worker or another worker host.

Start with the full step-by-step guide in [DEPLOYMENT.md](DEPLOYMENT.md).

The repository also contains `render.yaml`, a Render Blueprint for the free API, Postgres, and Key Value services. It intentionally leaves the worker commented out until a paid worker plan is selected.

The Oracle VM files remain as a legacy alternative:

- `compose.production.yaml`
- `deploy/Caddyfile`
- `deploy/bootstrap-ubuntu-arm64.sh`
