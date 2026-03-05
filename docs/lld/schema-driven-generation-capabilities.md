# LLD: Schema-Driven Generation Capabilities (Pydantic Envelope + JSON Schema Core)

## 1) Context and Goal

The current generation implementation is operation-driven (`TEXT_TO_IMAGE`, `IMAGE_TO_IMAGE`) and model-specific (Nano Banana mapper + static catalog).  
We need to support many image/video models (Veo, Kling, GPT Image, Nano Banana variants, etc.) where each model/operation has different input fields.

This LLD defines a backend design that:

- keeps API contracts strongly typed with Pydantic
- uses dynamic JSON Schema for model-specific inputs
- exposes model capabilities for UI rendering
- validates incoming model inputs server-side before provider submission
- supports fast onboarding of new models without backend redeploy for every field change

## 2) Key Decision

Use a **hybrid** approach:

- **Pydantic** for stable API envelopes and domain contracts.
- **JSON Schema** (from internal model registry) for dynamic `inputs` validation/rendering metadata.

Do **not** define one Pydantic request class per provider model/operation.

## 3) Scope

### In scope (this design)

- Capability discovery endpoint
- Dynamic input schema normalization for UI
- Generic generation submit envelope
- Server-side JSON schema validation for `inputs`
- Model allowlist and operation routing

### Out of scope (for later phases)

- Backward compatibility for old generation request payloads
- Multi-provider fallback
- Billing/quotas
- advanced workflow chaining

## 4) Current Constraints in Codebase

- Domain operation type is limited to image-only operations.
- DB check constraint for `generation_jobs.operation` only allows:
  - `TEXT_TO_IMAGE`
  - `IMAGE_TO_IMAGE`
- Existing catalog/mapper layer is static and Nano Banana-centric.

Implication: for video and multi-model support, operation must be generalized and schema-driven.

## 5) Proposed Backend Architecture

### 5.1 Components

1. `GenerationModelRegistry`
- Responsibility: internal allowlist of supported models and operations.
- Maps internal stable keys to Fal endpoint ids and stores operation input schemas.
- Source: local JSON file committed in repo.

2. `CapabilityNormalizer`
- Responsibility: convert registry-stored operation schemas into a UI-safe normalized schema format.
- Extracts required fields, field type, enum options, defaults, and descriptions.

3. `GenerationCapabilityService`
- Responsibility: produce capability response grouped by media type (`image`, `video`).
- Uses local in-memory cache with TTL.

4. `GenerationInputValidator`
- Responsibility: validate `inputs` against operation JSON schema before provider submission.
- Should use JSON Schema validation library.

5. `GenerationSubmissionService`
- Responsibility: resolve model+operation -> endpoint, validate inputs, submit to provider, persist job.

### 5.2 Data Flow

1. Client requests `GET /api/v1/generation/capabilities`.
2. Backend resolves allowlist and operation schemas from `model_registry.json`, caches parsed result with TTL, and normalizes response.
3. Client renders dynamic form from returned fields.
4. Client submits `POST /api/v1/collections/{collection_id}/items/generate` with `{modelKey, operationKey, inputs}`.
5. Backend validates `inputs` with JSON Schema.
6. Backend submits to resolved Fal endpoint and creates job record.

## 6) API Contracts (Pydantic)

### 6.1 Capability API

`GET /api/v1/generation/capabilities`

Response (stable envelope):

- `image: list[ModelCapability]`
- `video: list[ModelCapability]`

`ModelCapability`:
- `model: str` (display label)
- `modelKey: str` (stable internal key)
- `provider: str` (`fal`)
- `operations: list[OperationCapability]`

`OperationCapability`:
- `operationKey: str` (example: `text_to_image`, `image_to_video`)
- `endpointId: str`
- `required: list[str]`
- `fields: list[InputFieldCapability]`

`InputFieldCapability`:
- `key: str`
- `type: str` (`string`, `integer`, `number`, `boolean`, `array`, `object`, `union`)
- `required: bool`
- `description: str | null`
- `default: JsonValue | null`
- `enum: list[JsonValue] | null`
- `format: str | null` (optional)
- `itemsType: str | null` (for arrays)

### 6.2 Generation Submit API

`POST /api/v1/collections/{collection_id}/items/generate`

Request:
- `projectId: UUID`
- `modelKey: str`
- `operationKey: str`
- `inputs: dict[str, JsonValue]`
- `idempotencyKey: str | null`

Notes:
- `collectionId` comes from the path parameter.
- This replaces the existing operation-specific payload and is intentionally breaking.

Response:
- `jobId: UUID`
- `status: "QUEUED" | "IN_PROGRESS" | "SUCCEEDED" | "FAILED" | "CANCELLED"`
- `modelKey: str`
- `operationKey: str`

## 7) Generation Model Registry (Allowlist)

Maintain the allowlist as JSON:

- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.json`
- Loaded by `GenerationModelRegistry` and cached in-memory
- Strictly validated (JSON schema or equivalent strict validator)
- Reloaded from local file when cache TTL expires

One entry per product-visible model:

- each model has a stable internal `model_key`
- each model must declare `enabled` (boolean)
- each model contains supported operations
- each operation maps to a concrete provider endpoint id and a JSON input schema

Example shape:

```json
{
  "models": [
    {
      "model_key": "nano_banana",
      "display_name": "Nano Banana",
      "provider": "fal",
      "media_type": "image",
      "enabled": true,
      "operations": [
        {
          "operation_key": "text_to_image",
          "endpoint_id": "fal-ai/nano-banana",
          "input_schema": {
            "type": "object",
            "required": ["prompt"],
            "properties": {
              "prompt": { "type": "string" },
              "num_images": { "type": "integer", "default": 1 }
            },
            "additionalProperties": false
          }
        },
        {
          "operation_key": "image_to_image",
          "endpoint_id": "fal-ai/nano-banana/edit",
          "input_schema": {
            "type": "object",
            "required": ["prompt", "image_urls"],
            "properties": {
              "prompt": { "type": "string" },
              "image_urls": {
                "type": "array",
                "items": { "type": "string", "format": "uri" }
              }
            },
            "additionalProperties": false
          }
        }
      ]
    },
    {
      "model_key": "veo_3_1",
      "display_name": "Veo 3.1",
      "provider": "fal",
      "media_type": "video",
      "enabled": true,
      "operations": [
        {
          "operation_key": "text_to_video",
          "endpoint_id": "fal-ai/veo3.1",
          "input_schema": {
            "type": "object",
            "required": ["prompt"],
            "properties": {
              "prompt": { "type": "string" }
            },
            "additionalProperties": false
          }
        },
        {
          "operation_key": "image_to_video",
          "endpoint_id": "fal-ai/veo3.1/image-to-video",
          "input_schema": {
            "type": "object",
            "required": ["prompt", "image_url"],
            "properties": {
              "prompt": { "type": "string" },
              "image_url": { "type": "string", "format": "uri" }
            },
            "additionalProperties": false
          }
        }
      ]
    }
  ]
}
```

Why: internal keys remain stable even if provider endpoint names change, and product can control availability and schema without code edits or runtime provider fetches.

## 8) JSON Schema Handling

### 8.1 Source of truth

Operation input schemas are stored in `model_registry.json` and maintained manually by developers.

### 8.2 Normalization rules

For each operation endpoint:

- read `input_schema` from registry
- collect:
  - `required` array
  - `properties` entries
  - field type (`type` or `anyOf`)
  - enum/default/description

### 8.3 Validation

On submit:

1. resolve operation schema
2. validate input payload
3. reject unknown fields (strict whitelist, no provider pass-through)
4. return `400 validation_error` with structured field errors if invalid

### 8.4 Developer Workflow: Importing Schema from Fal (Manual)

Runtime behavior must not fetch schemas from Fal, but developers can fetch schemas manually when adding/updating models in `model_registry.json`.

#### Step 1: Fetch endpoint metadata + OpenAPI

```bash
curl -s \
  "https://api.fal.ai/v1/models?endpoint_id=fal-ai/veo3.1/image-to-video&expand=openapi-3.0" \
  -H "Authorization: Key $FAL_KEY" \
  > /tmp/fal_model.json
```

Notes:
- Auth is optional for many cases but recommended for higher rate limits.
- Replace endpoint id with the exact model operation endpoint you want.

#### Step 2: Extract request input schema

```bash
jq '
  .models[0].openapi as $o
  | ($o.paths | to_entries[] | select(.key | contains("requests") | not).value.post.requestBody.content["application/json"].schema) as $s
  | if ($s | has("$ref"))
      then $o.components.schemas[($s["$ref"] | sub("#/components/schemas/"; ""))]
      else $s
    end
' /tmp/fal_model.json > /tmp/fal_input_schema.json
```

#### Step 3: Copy into registry

- Paste the extracted schema into:
  - `models[].operations[].input_schema` in `model_registry.json`
- Ensure:
  - `model_key` is stable and product-friendly
  - `enabled` is explicitly set
  - `additionalProperties` behavior matches strict input policy (recommended: `false`)

#### Step 4: Validate and test

- Validate `model_registry.json` against `model_registry.schema.json`
- Run unit/API tests for capability rendering and submit validation
- Commit both registry changes and tests together

This workflow keeps production runtime deterministic while still allowing fast model onboarding.

## 9) Caching Strategy

### 9.1 Initial approach

- in-memory process cache
- cache value: parsed+validated `model_registry.json`
- cache key: registry file path
- refresh trigger: TTL expiry from settings (example `generation_registry_cache_ttl_seconds`)
- recommended default TTL: 300 seconds

### 9.2 Later improvements

- file `mtime` check optimization to avoid unnecessary reparsing
- optional dev-mode hot reload

## 10) Database and Domain Evolution (Single Table Only)

This design intentionally keeps generation persistence in one table: `generation_jobs`.

### 10.1 Schema changes in `generation_jobs`

Drop:

- Drop constraint `ck_generation_jobs_operation` (old fixed enum constraint).
- Do not drop data columns during this migration.

Rename columns:

- `operation` -> `operation_key`
- `request_payload` -> `inputs_json`
- `provider_response` -> `provider_response_json`

Add columns:

- `endpoint_id` (`VARCHAR(255)`, nullable initially, later `NOT NULL` after backfill)
- `outputs_json` (`JSONB`, `NOT NULL`, default `[]`)  
  stores normalized outputs inline: `[{index, media_type, provider_url, stored_url, metadata}]`
- `idempotency_key` (`VARCHAR(128)`, nullable)
- `registry_hash` (`VARCHAR(64)`, nullable)  
  hash/fingerprint of `model_registry.json` used at submission time

Keep existing columns:

- `provider`
- `model_key`
- `provider_request_id`
- `status`
- error fields and timestamps

### 10.2 Indexes and constraints

Add:

- Unique partial index on `provider_request_id` where not null (keep existing if already present)
- Unique partial index on `(project_id, collection_id, idempotency_key)` where not null
- Index on `(status, updated_at DESC)` for job reconciliation/polling
- Check constraint: `outputs_json` must be a JSON array

### 10.3 `GenerationRequest` domain object

Replace fixed operation-specific fields with generic schema-driven fields:

- `model_key: str`
- `operation_key: str`
- `inputs: JsonObject`
- `idempotency_key: str | None`

### 10.4 Migration policy

- This is a breaking migration aligned with the breaking API payload.
- Prefer rename over drop for existing columns to preserve historical records.
- Column drops are not required now.

## 11) Migration Plan (Breaking Change)

### Single rollout

- Replace generation request contract on:
  - `POST /api/v1/collections/{collection_id}/items/generate`
- Add:
  - `GET /api/v1/generation/capabilities`
- Generalize operation handling from fixed enum values to `operationKey`.
- Apply `generation_jobs` schema migration:
  - drop old operation constraint
  - rename old operation/request/response columns
  - add `endpoint_id`, `outputs_json`, `idempotency_key`, `registry_hash`
  - add new indexes/constraints
- Update frontend to consume capabilities and submit dynamic payload.
- Remove old operation-specific request assumptions in backend and frontend.

## 12) Error Contract

Use existing API error envelope style:

- `code`: machine-readable
- `message`: stable user-safe message
- `details.errors`: array of field-specific errors

Suggested codes:

- `unsupported_model_key`
- `unsupported_operation_key`
- `capability_registry_load_failed`
- `schema_validation_failed`
- `provider_submit_failed`

## 13) Testing Plan

### Unit tests

- registry JSON loading and schema validation
- field normalization logic
- JSON schema validation success/failure paths
- registry resolution (model/operation to endpoint)

### API tests

- capabilities endpoint returns grouped image/video models
- generation submit rejects invalid inputs with field-level errors
- generation submit rejects unsupported model/operation pairs

### Integration tests

- provider submission integration (mocked Fal responses)
- job persistence with generalized operation keys

## 14) Observability

Log fields for tracing:

- `model_key`
- `operation_key`
- `endpoint_id`
- `provider_request_id`
- validation failure summary

Metrics:

- registry cache hit/miss
- validation failures by model/operation
- submit success/failure by model/operation

## 15) Security Notes

- keep Fal API keys server-side only
- never trust client-sent schema
- validate all `inputs` server-side
- cap payload sizes and nested depth for `inputs`

## 16) Proposed Initial File Additions (for implementation thread)

- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry_loader.py`
- `src/ai_video_gen_backend/infrastructure/providers/fal/schema_normalizer.py`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.json`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json`
- `src/ai_video_gen_backend/application/generation/get_generation_capabilities.py`
- `src/ai_video_gen_backend/application/generation/validate_generation_inputs.py`
- `src/ai_video_gen_backend/presentation/api/v1/routers/generation_capabilities_router.py`
- `src/ai_video_gen_backend/presentation/api/v1/schemas/generation_capability_schema.py`
- `src/ai_video_gen_backend/presentation/api/v1/schemas/generation_submit_schema.py`

## 17) Open Questions (to settle before coding in next thread)

1. Confirm default `generation_registry_cache_ttl_seconds` (proposed: 300 seconds).
2. Should registry reload require restart, or support hot reload in development only?
