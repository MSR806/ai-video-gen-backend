# AI Video Gen Backend

FastAPI + PostgreSQL backend for the AI video generation platform.

## Stack
- Python 3.12
- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- S3-compatible object storage (external bucket + CDN/public URL)
- Ruff + MyPy + Pytest + pre-commit

## Setup

```bash
uv sync --all-extras
cp .env.example .env
uv run pre-commit install --install-hooks --hook-type pre-commit --hook-type commit-msg
```

Generation uses `fal-client` and requires `FAL_API_KEY` in `.env`.

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

Note: object storage is expected to be an external S3-compatible service configured via
`STORAGE_*` environment variables.

## Quality checks

```bash
uv run ruff format --check
uv run ruff check
uv run mypy src tests
uv run pytest -q
```

## Coverage report

```bash
source .venv/bin/activate
uv run --with coverage coverage erase
uv run --with coverage coverage run --source=src/ai_video_gen_backend -m pytest -q
uv run --with coverage coverage report -m
```

## Commit message format

Conventional Commits are enforced via `gitlint` as a `commit-msg` hook.

Valid examples:
- `feat(screenplay): add screenplay sync endpoint`
- `fix: handle empty upload payload`

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
- `GET /api/v1/generation/capabilities`
- `GET /api/v1/generation-jobs/{job_id}`
- `POST /api/v1/provider-webhooks/fal`
- `DELETE /api/v1/collections/{collection_id}/items/{item_id}`
- `GET /api/v1/projects/{project_id}/screenplays`
- `POST /api/v1/projects/{project_id}/screenplays`
- `PATCH /api/v1/projects/{project_id}/screenplays`
- `POST /api/v1/projects/{project_id}/screenplays/scenes`
- `PATCH /api/v1/projects/{project_id}/screenplays/scenes/{scene_id}`
- `DELETE /api/v1/projects/{project_id}/screenplays/scenes/{scene_id}`
- `POST /api/v1/projects/{project_id}/screenplays/scenes/reorder`
- `GET /health/live`
- `GET /health/ready`

`POST /api/v1/projects/{project_id}/collections` accepts optional `parentCollectionId` to create a
nested collection under another collection in the same project.

`GET /api/v1/collections/{collection_id}/items` returns an object with `items` and
`childCollections` (breaking change from prior list-only response).

`POST /api/v1/collections/{collection_id}/items/generate` is asynchronous and returns `202` with
`jobId`, `status`, `modelKey`, and `operationKey`. Use `GET /api/v1/generation-jobs/{job_id}` to
track status.
