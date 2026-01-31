# Auction OCR

Internal web app for processing USS auction sheet images with OCR.

## Prereqs

- uv 0.9+
- bun 1.3+
- Docker (optional for local stack)

## Local development

1. Copy env template:

```bash
cp .env.example .env
```

2. Start the dev stack with Docker Compose:

```bash
docker compose up --build
```

Services:
- API: http://localhost:8000/health
- Frontend: http://localhost:3000
- MinIO console: http://localhost:9001

Run migrations:

```bash
cd backend
uv run alembic upgrade head
```

## Run backend locally (without Docker)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run worker locally (without Docker)

```bash
cd backend
uv sync
uv run celery -A worker.celery_app worker --loglevel=INFO
```

## Run frontend locally (without Docker)

```bash
cd frontend
bun install
bun run dev
```
