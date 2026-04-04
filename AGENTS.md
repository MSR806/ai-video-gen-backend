# Backend Agent Rules - Python Clean Architecture

## Core Principles

Dependency direction is strictly enforced: `presentation -> application -> domain` and `infrastructure -> domain`.

- **Domain layer** is pure Python only. No FastAPI, SQLAlchemy, httpx, or any transport/framework import is allowed here.
- **Application layer** orchestrates use-cases. It imports **only** from `domain`. It must never import from `infrastructure` or `presentation`.
- **Infrastructure layer** implements domain ports. It may import from `domain` and third-party libraries.
- **Presentation layer** wires dependencies. It imports from `application`, `domain`, `infrastructure`, and FastAPI.

Any import that violates this direction is a hard error. Do not work around it with `TYPE_CHECKING` guards or conditional imports.

## Feature-First Structure

- Organize by feature: `project`, `collection`, `collection_item`, `screenplay`, `generation`.
- Each feature defines entities and `Protocol`-based repository/service ports in `domain/<feature>/`.
- Use-cases live in `application/<feature>/`.
- SQLAlchemy models and repository implementations live in `infrastructure/repositories/`.
- Third-party provider adapters live in `infrastructure/providers/`.
- API schemas and routers live in `presentation/api/v1/`.

## Domain Port Rules

- All ports are defined as `typing.Protocol` in `domain/<feature>/ports.py` (or a dedicated file like `domain/<feature>/downloader.py`).
- Every method that a concrete infrastructure adapter implements **must** appear on the port. If the application layer needs a method, add it to the port first.
- Ports must not expose provider-specific concepts (e.g. `endpoint_id`, SDK types, HTTP clients). Use abstracted parameters (e.g. `model_key`).
- Shared scalar types (`JsonValue`, `JsonObject`) live exclusively in `domain/types.py`. Never redefine them in entity files; import them from there.
- Entity files that re-export types from `domain/types.py` must declare them in `__all__` to satisfy the linter.

## Forbidden Patterns

The following are **never** allowed:

- Importing a concrete infrastructure class (e.g. `CollectionItemSqlRepository`, `FalGenerationProvider`) inside `application/`.
- Importing `httpx`, `boto3`, `fal_client`, `sqlalchemy`, or any I/O library inside `application/` or `domain/`.
- Calling provider-specific resolution logic (e.g. `resolve_model_key`, `get_model_profile`) inside `application/`. Delegate via a port method instead.
- Defining `JsonValue` or `JsonObject` in more than one place. Always import from `domain/types.py`.
- Adding methods to a concrete repository without also declaring them on the corresponding `Protocol` port.

## Database Rules

- PostgreSQL is the primary database for all environments except lightweight unit tests.
- Schema changes must go through Alembic migrations only. Never modify tables manually.
- Screenplay sync must be atomic per project (single transaction).

## Dependency Assumptions

- Required runtime dependencies are guaranteed by the Docker image/build.
- Do not add runtime import guards for required packages (e.g. wrapping `import fal_client` in `try/except`).

## API Contract Rules

- All request models use strict validation (`extra=forbid`).
- Error responses must follow the standard envelope: `error.code`, `error.message`, `error.details` (optional).
- Use UUID strings for public identifiers.

## Typing and Quality

- Strict mypy mode is mandatory. Zero mypy errors are required before commit.
- `Any` is forbidden in `domain/` and `application/`. Use specific types or `object` with narrowing.
- All public functions and methods must have explicit return type annotations.
- Keep modules focused and cohesive — one use-case class per file.

## Mandatory Test Requirements

Every code change must be accompanied by tests. The following coverage is required:

### New domain port method
- Add the method to the corresponding fake/stub in all test files that use that port.
- The fake must implement the full `Protocol` to prevent mypy `arg-type` errors.

### New use-case
- Unit test in `tests/unit/test_<use_case_name>.py` covering:
  - Happy path with a fake repository/port.
  - At least one failure mode (missing entity, provider error, etc.).
- The test must not import any infrastructure class. Use handwritten fakes that implement the domain port.

### New infrastructure adapter (port implementation)
- Unit test in `tests/unit/` covering the adapter's core logic with a monkeypatched or fake SDK client.
- Integration test in `tests/integration/` if the adapter touches the database.

### New API endpoint
- API test in `tests/api/` covering:
  - Success response shape and status code.
  - 404 / 400 / 422 failure modes.
  - Dependency override using `app.dependency_overrides` — never call real external services in tests.

### Modified port signature
- All fakes implementing that port in `tests/` must be updated to match.
- Run `uv run mypy src tests` to confirm no `arg-type` or `attr-defined` errors remain.

## Workflow and Gatekeeping

Before every commit, all four gates must pass with zero errors:

```
uv run ruff format --check
uv run ruff check
uv run mypy src tests
uv run pytest -q
```

- `ruff format --check` must report no files to reformat.
- `ruff check` must report 0 errors (auto-fix with `--fix` is allowed, but review the diff).
- `mypy` must report `Success: no issues found`.
- `pytest` must pass all tests with no failures or errors.

Commit messages must follow Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, etc.), enforced by `gitlint` in the `commit-msg` hook. Pre-commit hooks must pass before push.

## Git Commit Guidelines (Mandatory)

1. Commit flow:
- Run commits from this repo root only (`ai-video-gen-backend`).
- Activate environment first: `source .venv/bin/activate`.
- Run: `uv run pre-commit run --all-files` before `git commit`.

2. If hook tooling is missing:
- Run `uv sync --extra dev`.
- Rerun `uv run pre-commit run --all-files`.
- Commit only after hooks and checks pass.

3. Hook policy:
- Do not use `git commit --no-verify` unless the user explicitly instructs it.
- Treat hook failures as blockers and fix them before commit.

4. Commit message policy:
- Use Conventional Commit format.
- Keep message aligned with actual diff scope.
