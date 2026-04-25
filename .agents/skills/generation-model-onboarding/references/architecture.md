# Architecture Reference

## Design Principles

- **Pydantic** for stable request/response envelopes and domain contracts
- **Local JSON Schema** for operation-specific `inputs`
- **Repo-committed Fal registry** as the source of truth for supported models and operations
- **Schema normalization** to expose UI-safe field metadata
- **Server-side input validation** before provider submission

Schemas are never fetched from Fal at runtime. Runtime behavior is deterministic and depends only on committed registry files shipped with the backend deploy.

## Components

### `ModelRegistryLoader`

- Loads every `*.json` file from the `model_registry/` directory
- Validates each file against `model_registry.schema.json`
- Validates operation schema semantics by running the schema normalizer during load
- Sorts models by `sort_order`
- Fails fast on invalid registry changes — capability loading returns a controlled error

### `FalGenerationModelRegistry`

- Exposes grouped image/video capabilities
- Resolves `model_key + operation_key` to a concrete Fal endpoint and schema
- Uses the loader snapshot cache

### `schema_normalizer`

- Converts JSON-schema-like operation definitions into normalized `InputFieldCapability` objects
- Preserves UI-safe metadata: `title`, `description`, `default`, `enum`, `format`, `minimum`, `maximum`, `uiGroup`
- Parses and validates declarative media metadata

### `GenerationInputValidator`

- Validates submitted `inputs` against the resolved operation schema
- Rejects unknown fields — registry schemas use `additionalProperties: false`

### `SubmitGenerationRunUseCase`

1. Resolves the selected operation from `model_key + operation_key`
2. Validates `inputs` via `GenerationInputValidator`
3. Submits to the Fal endpoint
4. Persists the run using the generic `model_key` / `operation_key` contract

## Runtime Flow

```
GET /api/v1/generation/capabilities
  → Load local registry snapshot from model_registry/
  → Normalize operation schemas into field capabilities + media groups
  → Return grouped image/video capability payload

POST /api/v1/collections/{collection_id}/items/generate
  → Resolve model_key + operation_key
  → Validate inputs against resolved schema
  → Submit to Fal endpoint
  → Create generation placeholders
  → Return run status
```

## Caching

Two layers:

1. `get_generation_capability_registry()` — memoized with `lru_cache` at the service level
2. `ModelRegistryLoader` — caches the parsed registry snapshot for `generation_registry_cache_ttl_seconds`

Behavior:

- Registry files are re-read after the TTL window expires
- No backend restart required for local registry edits once the TTL passes
- Invalid registry changes cause capability loading to fail with a controlled error (not a silent stale cache)

