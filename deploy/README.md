# Oracle VM Deployment

This directory contains the first production deployment path for the VectoryAI backend. The target is an Oracle Cloud Always Free Ampere A1 ARM64 VM.

## 1. Create the VM

In Oracle Cloud Infrastructure:

1. Create an Ubuntu ARM64 VM using `VM.Standard.A1.Flex`.
2. Allocate up to 2 OCPUs and 12 GB RAM to one instance.
3. Assign a public IPv4 address.
4. Add ingress rules for TCP `22`, `80`, and `443` only.
5. Keep PostgreSQL `5432`, Redis `6379`, and application port `8000` closed to the public internet.

The free capacity is subject to regional availability. The A1 instance is ARM64, so images and Python dependencies must support `linux/arm64`.

## 2. Point DNS to the VM

Create an `A` record such as:

```text
api.example.com -> <VM public IPv4 address>
```

Caddy obtains and renews the HTTPS certificate automatically after DNS resolves and ports `80`/`443` are reachable.

## 3. Install Docker

From the repository root on the VM:

```bash
chmod +x deploy/bootstrap-ubuntu-arm64.sh
./deploy/bootstrap-ubuntu-arm64.sh
```

Log out and back in after the script finishes so the current user receives Docker group access.

## 4. Configure and start

```bash
cp deploy/.env.production.example .env.production
nano .env.production
docker compose --env-file .env.production -f compose.production.yaml up -d --build
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml logs -f api worker proxy
```

Set `CORS_ORIGINS` to include the deployed UI origin:

```text
CORS_ORIGINS=https://peterciprian.github.io/VectorAI
```

The API health endpoint should then respond at `https://api.example.com/health`.

## Updates

```bash
git pull --ff-only
docker compose --env-file .env.production -f compose.production.yaml up -d --build
```

## Backups and limits

Named volumes survive container recreation, but they are not backups. Back up PostgreSQL and project artifacts separately. The Always Free VM has limited CPU, RAM, and storage; the worker is intentionally configured with `--concurrency=1`. Heavy GPU models should move to a separate worker host later.
