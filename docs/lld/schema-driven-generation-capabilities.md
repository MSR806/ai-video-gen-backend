# LLD: Schema-Driven Generation Capabilities

## 1) Context and Goal

The backend now supports multiple Fal image and video models whose request schemas vary by
operation. The goal of this design is to keep the public API stable while allowing product-visible
model capabilities to be driven by local registry data instead of hardcoded provider mappers.

This document describes the current backend design, not the original proposal.

## 2) Current Design Summary

The implemented system uses a hybrid approach:

- **Pydantic** for stable request/response envelopes and domain contracts
- **Local JSON Schema** for operation-specific `inputs`
- **A repo-committed Fal registry** as the source of truth for supported models and operations
- **Schema normalization** to expose UI-safe field metadata
- **Server-side input validation** before provider submission

Important constraint: schemas are **not** fetched from Fal at runtime. Runtime behavior is
deterministic and only depends on the committed registry files shipped with the backend deploy.

## 3) Key Decisions

### 3.1 Stable operation identity vs semantic type

Each operation now carries three distinct identifiers:

- `operation_key`: unique within a model and used for backend resolution/submission
- `operation_type`: semantic category such as `text_to_video` or `image_to_video`
- `operation_name`: user-facing label exposed to the frontend

This allows multiple variants of the same semantic operation under one model, for example:

- `text_to_video`
- `text_to_video_fast`

Both can share `operation_type: "text_to_video"` while keeping unique `operation_key` values.

### 3.2 One registry file per model

The old monolithic `model_registry.json` was replaced with one JSON file per top-level model under:

- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/`

This keeps the registry maintainable as more models and operations are added.

### 3.3 Declarative UI/media metadata lives in `input_schema`

Operation schemas can now include backend-validated `x_ui_*` metadata. The most important cases are:

- `x_ui_group`
- `x_ui_media_groups`
- `x_ui_media_group`
- `x_ui_media_order`
- `x_ui_media_name`

These extensions are stored with the schema so the backend remains the source of truth for both
validation metadata and structured UI hints.

## 4) Implemented Architecture

### 4.1 Main components

1. `ModelRegistryLoader`
- Loads every `*.json` file from the Fal registry directory
- Validates each model file against `model_registry.schema.json`
- Validates operation schema semantics by running the schema normalizer during load
- Sorts models by `sort_order`

2. `FalGenerationModelRegistry`
- Exposes grouped image/video capabilities
- Resolves `model_key + operation_key` to a concrete Fal endpoint and schema
- Uses the loader snapshot cache

3. `schema_normalizer`
- Converts JSON-schema-like operation definitions into normalized field capabilities
- Preserves UI-safe metadata such as `title`, `description`, `default`, `enum`, `format`,
  `minimum`, `maximum`, and `uiGroup`
- Parses and validates declarative media metadata

4. `GenerationInputValidator`
- Validates submitted `inputs` against the resolved operation schema
- Rejects unknown fields because registry schemas are strict (`additionalProperties: false`)

5. `SubmitGenerationRunUseCase`
- Resolves the selected operation
- Validates the inputs
- Submits to the provider
- Persists the run using the generic `model_key` / `operation_key` contract

### 4.2 Runtime flow

1. Client requests `GET /api/v1/generation/capabilities`
2. Backend loads the local registry snapshot from the model registry directory
3. Backend normalizes operation schemas into field capabilities plus media groups
4. Client renders the form from the returned capability payload
5. Client submits `POST /api/v1/collections/{collection_id}/items/generate`
6. Backend resolves `model_key + operation_key`
7. Backend validates `inputs` against the resolved schema
8. Backend submits to the Fal endpoint and creates generation placeholders

## 5) Registry Layout

### 5.1 Registry files

Current registry files live here:

- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/nano_banana.json`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/nano_banana_pro.json`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/nano_banana_2.json`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/veo_3_1.json`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/kling_video_2_6_pro.json`

Each file defines exactly one product-visible model.

### 5.2 Required model shape

Each model file must define:

- `sort_order`
- `model_key`
- `display_name`
- `provider`
- `media_type`
- `enabled`
- `operations`

Each operation must define:

- `operation_key`
- `operation_type`
- `operation_name`
- `endpoint_id`
- `input_schema`

`operation_key` must be unique within the model file.

### 5.3 Example shape

```json
{
  "sort_order": 20,
  "model_key": "veo_3_1",
  "display_name": "Veo 3.1",
  "provider": "fal",
  "media_type": "video",
  "enabled": true,
  "operations": [
    {
      "operation_key": "first_last_frame_to_video_fast",
      "operation_type": "first_last_frame_to_video",
      "operation_name": "First/Last Frame to Video (Fast)",
      "endpoint_id": "fal-ai/veo3.1/fast/first-last-frame-to-video",
      "input_schema": {
        "type": "object",
        "x_ui_media_groups": [
          {
            "group_key": "frames",
            "layout": "sequence",
            "placement": "top"
          }
        ],
        "required": ["prompt", "first_frame_url", "last_frame_url"],
        "properties": {
          "prompt": {
            "type": "string",
            "description": "The text prompt describing the video you want to generate."
          },
          "first_frame_url": {
            "x_ui_media_group": "frames",
            "x_ui_media_order": 1,
            "x_ui_media_name": "Start",
            "type": "string",
            "format": "uri",
            "description": "URL of the first frame of the video."
          },
          "last_frame_url": {
            "x_ui_media_group": "frames",
            "x_ui_media_order": 2,
            "x_ui_media_name": "End",
            "type": "string",
            "format": "uri",
            "description": "URL of the last frame of the video."
          }
        },
        "additionalProperties": false
      }
    }
  ]
}
```

## 6) Capability API Contract

### 6.1 Capability endpoint

`GET /api/v1/generation/capabilities`

Response:

- `image: list[ModelCapability]`
- `video: list[ModelCapability]`

`ModelCapability`:

- `model: str`
- `modelKey: str`
- `provider: str`
- `operations: list[OperationCapability]`

`OperationCapability`:

- `operationKey: str`
- `operationType: str`
- `operationName: str`
- `endpointId: str`
- `required: list[str]`
- `fields: list[InputFieldCapability]`
- `mediaGroups: list[MediaGroupCapability]`

`InputFieldCapability`:

- `key: str`
- `type: str`
- `required: bool`
- `uiGroup: str | null`
- `title: str | null`
- `description: str | null`
- `default: JsonValue | null`
- `enum: list[JsonValue] | null`
- `format: str | null`
- `itemsType: str | null`
- `minimum: JsonValue | null`
- `maximum: JsonValue | null`
- `mediaGroup: str | null`
- `mediaOrder: int | null`
- `mediaName: str | null`

`MediaGroupCapability`:

- `groupKey: str`
- `layout: "single" | "sequence" | "gallery"`
- `placement: "top"`

### 6.2 Generation submit API

`POST /api/v1/collections/{collection_id}/items/generate`

Request:

- `projectId: UUID`
- `modelKey: str`
- `operationKey: str`
- `inputs: dict[str, JsonValue]`
- `outputCount: int` (default `1`)
- `idempotencyKey: str | null`

Response:

- `runId: UUID`
- `status: "QUEUED" | "IN_PROGRESS" | "SUCCEEDED" | "PARTIAL_FAILED" | "FAILED" | "CANCELLED"`
- `modelKey: str`
- `operationKey: str`
- `outputs: list[{outputId, outputIndex, status, collectionItemId}]`

## 7) Schema Normalization Rules

The normalizer converts `input_schema.properties` into stable field capability objects.

Preserved metadata:

- `type`
- `required`
- `title`
- `description`
- `default`
- `enum`
- `format`
- `itemsType`
- `minimum`
- `maximum`
- `x_ui_group`
- `x_ui_media_group`
- `x_ui_media_order`
- `x_ui_media_name`

The backend keeps the schema strict:

- `additionalProperties: false` is expected for registry-managed schemas
- unknown fields are rejected on submit
- URI fields are exposed with `format: "uri"` so the frontend can treat them as media inputs

## 8) Declarative Media Metadata

### 8.1 Root-level media groups

`input_schema` may define:

```json
"x_ui_media_groups": [
  {
    "group_key": "frames",
    "layout": "sequence",
    "placement": "top"
  }
]
```

### 8.2 Field-level media annotations

URI fields can join a media group with:

- `x_ui_media_group`
- `x_ui_media_order`
- `x_ui_media_name`

### 8.3 Supported layouts

Current validated layouts:

- `single`
- `sequence`
- `gallery`

Current validated placement:

- `top`

### 8.4 Semantic validation rules

The backend fails fast if media metadata is inconsistent.

Rules:

- referenced media groups must exist
- every declared group must have at least one member field
- `single` groups must contain exactly one URI string field
- `gallery` groups must contain exactly one URI-array field whose items are URI strings
- `sequence` groups must contain URI string fields with unique `x_ui_media_order`
- `x_ui_media_order` and `x_ui_media_name` cannot appear without `x_ui_media_group`

This validation happens in the backend loader path, not in the frontend.

## 9) Developer Workflow for Adding or Updating Models

### 9.1 Source of truth

Fal schemas are copied into the local registry manually. Runtime must not fetch provider schemas.

### 9.2 Suggested workflow

1. Get the provider schema from Fal documentation or model metadata
2. Copy the request schema into the appropriate model file under `model_registry/`
3. Normalize provider-specific quirks into the local strict format:
   - flatten nullable fields into optional local fields
   - preserve `title`, `description`, `default`, `enum`, `minimum`, `maximum`
   - keep `additionalProperties: false`
   - mark URLs with `format: "uri"`
4. Add UI metadata where needed:
   - `x_ui_group` for basic vs advanced settings
   - `x_ui_media_*` for declarative media layout
5. Validate with tests and commit registry plus tests together

### 9.3 How to add a new model

Use this flow when onboarding a new Fal model or a new Fal operation under an existing model.

1. Decide whether this is:
   - a new top-level product model, which needs a new file in `model_registry/`
   - a new operation variant for an existing product model, which should be added to that model's
     existing file
2. Use Fal's `llms.txt` page as the source document for the schema. The pattern is:
   - `https://fal.ai/models/<endpoint_id>/llms.txt`
3. For example, the schema source for Kling image-to-video is:
   - `https://fal.ai/models/fal-ai/kling-video/v2.6/pro/image-to-video/llms.txt`
4. Copy the request schema details from that document into the local registry operation entry:
   - set `operation_key`
   - set `operation_type`
   - set `operation_name`
   - set `endpoint_id`
   - set `input_schema`
5. Normalize the copied schema into the local strict format:
   - use JSON object schema shape under `input_schema`
   - preserve `title`, `description`, `default`, `enum`, `minimum`, and `maximum`
   - make nullable provider fields optional local fields
   - add `format: "uri"` to URL fields
   - keep `additionalProperties: false`
6. Add backend-owned UI metadata where appropriate:
   - `x_ui_group: "advanced"` for fields that should not show by default
   - `x_ui_media_groups` plus field-level `x_ui_media_group`, `x_ui_media_order`, and
     `x_ui_media_name` for top media inputs
7. If this is a new model file, define model-level metadata too:
   - `sort_order`
   - `model_key`
   - `display_name`
   - `provider`
   - `media_type`
   - `enabled`
8. Validate locally:
   - registry schema validation
   - registry loader tests
   - capability API tests
9. Commit the registry update and tests together

### 9.4 What changes require code vs registry only

Registry-only:

- adding a new field
- changing field labels/descriptions/defaults
- reclassifying a field as advanced
- changing media slot labels or sequence order
- adding a new operation for an existing rendering pattern

Backend/frontend code changes:

- introducing a new capability field not already exposed
- introducing a new media layout beyond `single`, `sequence`, or `gallery`
- changing the public API contract

## 10) Caching and Reloading

The registry uses two layers of caching:

1. `get_generation_capability_registry()` memoizes the registry service with `lru_cache`
2. `ModelRegistryLoader` caches the parsed snapshot for `generation_registry_cache_ttl_seconds`

Current behavior:

- registry files are re-read after TTL expiry
- no backend restart is required for local registry edits once the TTL window passes
- invalid registry changes fail capability loading fast with a controlled backend error

## 11) Error Contract

Relevant API error codes:

- `unsupported_model_key`
- `unsupported_operation_key`
- `capability_registry_load_failed`
- `schema_validation_failed`
- `provider_submit_failed`

Capability-loading failures are intentionally coarse at the API layer, while the backend logs and
tests should expose the specific registry/normalization failure.

## 12) Testing Strategy

### Unit tests

- registry file loading and schema validation
- duplicate `operation_key` rejection
- schema normalization and field metadata extraction
- media metadata semantic validation
- operation resolution from `model_key + operation_key`

### API tests

- capability endpoint returns grouped image/video models
- capability payload includes `operationType`, `operationName`, `mediaGroups`, `mediaGroup`,
  `mediaOrder`, and `mediaName`
- submit rejects invalid inputs with field-level errors

### Frontend-facing contract tests (backend-owned impact)

- URI media fields continue to surface `format: "uri"`
- `title`, `minimum`, and `maximum` metadata remain available to the UI

## 13) Observability and Security Notes

Log fields:

- `model_key`
- `operation_key`
- `endpoint_id`
- `provider_request_id`
- validation failure summaries

Security rules:

- keep Fal credentials server-side only
- never trust client-supplied schema information
- validate all `inputs` against the resolved registry schema
- keep schemas strict and provider allowlists local

## 14) Relevant Implemented Files

- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry_loader.py`
- `src/ai_video_gen_backend/infrastructure/providers/fal/schema_normalizer.py`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/`
- `src/ai_video_gen_backend/application/generation/get_generation_capabilities.py`
- `src/ai_video_gen_backend/application/generation/validate_generation_inputs.py`
- `src/ai_video_gen_backend/presentation/api/v1/routers/generation_capabilities_router.py`
- `src/ai_video_gen_backend/presentation/api/v1/schemas/generation_capability_schema.py`
- `src/ai_video_gen_backend/presentation/api/v1/schemas/generation_submit_schema.py`
