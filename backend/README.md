# WMS Backend Core

FastAPI + SQLAlchemy 2.x (async) + PostgreSQL backend for a Warehouse Management System.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker with BuildKit

## Local development

```bash
cp .env.example .env            # set POSTGRES_PASSWORD and JWT_SECRET
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

- Docs: http://localhost:8000/api/v1/docs
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready

Generate a JWT secret with `openssl rand -hex 32`.

## Tests

```bash
uv run pytest
```

## Docker

```bash
docker compose up -d --build
```

Compose reads `POSTGRES_PASSWORD` and `JWT_SECRET` from `.env`. PostgreSQL and the API
bind to localhost only. The image uses a two-stage build: uv builds the virtualenv,
then it is copied into a slim Python runtime running as a non-root user.

Health lives in the app, not in the image: point your orchestrator or load balancer at
`/api/v1/health/live` and `/api/v1/health/ready`.

## Production notes

- Set `ENVIRONMENT=production`; docs are disabled automatically.
- Rotate `JWT_SECRET` and database credentials; use a dedicated database role.
- Terminate TLS at a reverse proxy and keep CORS origins explicit.
- Add Alembic before shipping schema changes.
