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
uv run alembic upgrade head
uv run python -m scripts.create_admin --email admin@example.com
uv run uvicorn app.main:app --reload --port 8000
```

`create_admin` reads the password from `BOOTSTRAP_ADMIN_PASSWORD` or prompts for it.

- Docs: http://localhost:8000/api/v1/docs
- Liveness: http://localhost:8000/api/v1/health/live
- Readiness: http://localhost:8000/api/v1/health/ready

Generate a JWT secret with `openssl rand -hex 32`.

## Tests

Integration tests run against a real PostgreSQL database. By default the suite uses
`POSTGRES_DB=wms_test`, creating the database and applying migrations automatically.

```bash
uv run pytest
```

To point the suite at another database, set `TEST_DATABASE_URL` (or `TEST_POSTGRES_DB`).
Never point it at the development database: tables are truncated between tests.

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
- Apply schema changes with `uv run alembic upgrade head` during deployment.
- Create the first administrator with the bootstrap script, then disable the script's
  database credentials or run it from a controlled environment.
