# Backend Agent Rules - Python Clean Architecture

## Core Principles
- Enforce Clean Architecture dependency direction: `presentation -> application -> domain` and `infrastructure -> domain`.
- Domain layer is pure Python: no FastAPI, SQLAlchemy, or transport concerns.
- Application layer orchestrates use-cases and transactions; it does not know framework details.
- Infrastructure layer implements ports and external integrations.

## Feature-First Structure
- Organize by feature: `project`, `collection`, `collection_item`, `scene`.
- Each feature defines entities and repository ports in `domain/`.
- Use-cases live in `application/<feature>/`.
- SQLAlchemy models and repository implementations live in `infrastructure/`.
- API schemas and routers live in `presentation/api/v1/`.

## Database Rules
- PostgreSQL is the primary database for all environments except lightweight tests.
- Schema changes must go through Alembic migrations only.
- Never modify production tables manually.
- Scene sync must be atomic per project (single transaction).

## API Contract Rules
- All request models use strict validation (`extra=forbid`).
- Error responses must follow the standard envelope:
  - `error.code`
  - `error.message`
  - `error.details` (optional)
- Use UUID strings for public identifiers.

## Typing and Quality
- Strict mypy mode is mandatory.
- Avoid `Any` in domain and application layers.
- Use explicit return types for all public functions.
- Keep modules focused and cohesive.

## Testing Expectations
- Unit tests for use-cases and normalization logic.
- Integration tests for repository/database behavior.
- API tests for contract behavior and failure modes.

## Workflow and Gatekeeping
- Before commit, run quality gates:
  - `uv run ruff format --check`
  - `uv run ruff check`
  - `uv run mypy src tests`
  - `uv run pytest -q`
- Pre-commit hooks must pass before push.
