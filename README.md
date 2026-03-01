# AI Video Gen Backend

FastAPI + PostgreSQL backend for the AI video generation platform.

## Stack
- Python 3.12
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- MinIO (S3-compatible object storage)
- Ruff + MyPy + Pytest + pre-commit

## Setup

```bash
uv sync --all-extras
cp .env.example .env
```

For local (non-Docker) video uploads with thumbnails, `ffmpeg` must be installed and available in
your `PATH` (or configured via `VIDEO_THUMBNAIL_FFMPEG_BIN`).

## Run locally (without Docker)

```bash
uv run alembic upgrade head
uv run uvicorn ai_video_gen_backend.main:app --reload
```

## Run with Docker Compose

```bash
docker compose up --build
```

This brings up:
- API on `http://localhost:8000`
- Postgres on `localhost:5432`
- MinIO S3 API on `http://localhost:9000`
- MinIO Console on `http://localhost:9001`

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
- `POST /api/v1/collections/{collection_id}/items/upload`
- `POST /api/v1/collections/{collection_id}/items/generate`
- `DELETE /api/v1/collections/{collection_id}/items/{item_id}`
- `GET /api/v1/projects/{project_id}/scenes`
- `PUT /api/v1/projects/{project_id}/scenes`
- `GET /health/live`
- `GET /health/ready`
