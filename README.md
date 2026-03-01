# AI Video Gen Backend

FastAPI + PostgreSQL backend for the AI video generation platform.

## Stack
- Python 3.12
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Ruff + MyPy + Pytest + pre-commit

## Setup

```bash
uv sync --all-extras
cp .env.example .env
```

## Run locally (without Docker)

```bash
uv run alembic upgrade head
uv run uvicorn ai_video_gen_backend.main:app --reload
```

## Run with Docker Compose

```bash
docker compose up --build
```

## Quality checks

```bash
uv run ruff format --check
uv run ruff check
uv run mypy src tests
uv run pytest -q
```

## API
Base path: `/api/v1`

- `GET /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/collections`
- `GET /api/v1/collections/{collection_id}`
- `GET /api/v1/collections/{collection_id}/items`
- `POST /api/v1/collections/{collection_id}/items`
- `POST /api/v1/collections/{collection_id}/items/generate`
- `GET /api/v1/projects/{project_id}/scenes`
- `PUT /api/v1/projects/{project_id}/scenes`
- `GET /health/live`
- `GET /health/ready`
