ARG PYTHON_VERSION=3.13.18
ARG UV_VERSION=0.13.7

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# Stage 1: build the virtual environment with uv
FROM python:${PYTHON_VERSION}-slim-trixie AS builder

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock,readonly \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml,readonly \
    uv sync --locked --no-install-project --no-dev

# Stage 2: runtime image without uv or build tools
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app app ./app

USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
