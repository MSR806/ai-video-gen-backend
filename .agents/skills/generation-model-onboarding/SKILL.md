---

## name: generation-model-onboarding

description: Guide for adding or updating AI generation models and operations in the backend registry. Use when adding a new Fal model, adding a new operation variant, updating input schemas, adding media groups, or changing UI metadata in the model registry. Triggers include "add a model", "add an operation", "update the registry", "add media input", "schema-driven", or any work touching model_registry files or the capabilities API.

# Schema-Driven Generation

The backend exposes AI generation capabilities through a local registry — no runtime provider schema fetching. All changes to supported models and operations are registry-only unless a new capability type is introduced.

## Key Files

- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry/` — one JSON file per model
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry_loader.py`
- `src/ai_video_gen_backend/infrastructure/providers/fal/schema_normalizer.py`
- `src/ai_video_gen_backend/infrastructure/providers/fal/model_registry.schema.json`
- `src/ai_video_gen_backend/application/generation/get_generation_capabilities.py`
- `src/ai_video_gen_backend/application/generation/validate_generation_inputs.py`
- `src/ai_video_gen_backend/presentation/api/v1/routers/generation_capabilities_router.py`
- `src/ai_video_gen_backend/presentation/api/v1/schemas/generation_capability_schema.py`
- `src/ai_video_gen_backend/presentation/api/v1/schemas/generation_submit_schema.py`

## Adding a New Model or Operation

**Step 1 — Get the provider schema**

For Fal models, fetch from `https://fal.ai/models/<endpoint_id>/llms.txt` and translate the schema into the local registry format. See [references/fal-schema-translation.md](references/fal-schema-translation.md) for the full translation guide.

**Step 2 — New file or existing file?**

- New top-level product model → create `model_registry/<model_key>.json`
- New operation variant under an existing model → add to the existing model file

**Step 3 — Write the registry entry**

See [references/registry-schema.md](references/registry-schema.md) for required fields, schema normalization rules, and a complete example.

**Step 4 — Add UI metadata**

- `x_ui_group: "advanced"` for fields hidden by default
- For media inputs, add `x_ui_media_groups` (root) and `x_ui_media_group` / `x_ui_media_order` / `x_ui_media_name` (field-level)

See [references/registry-schema.md](references/registry-schema.md) for media group layout rules and validation constraints.

**Step 5 — Validate and commit**

Run registry loader tests, capability API tests, and commit the registry file + tests together. See [references/testing.md](references/testing.md) for what to test.

## Registry-Only vs Code Changes

**Registry-only** — no logic changes needed:

- Add/modify fields, labels, descriptions, defaults
- Reclassify a field as advanced
- Add a new operation for an existing rendering pattern
- Change media slot labels or sequence order

**Requires backend/frontend code changes:**

- New capability field not yet in `InputFieldCapability`
- New media layout beyond `single`, `sequence`, `gallery`
- Changes to the public API contract

## Testing Checklist

- Registry schema validation passes
- No duplicate `operation_key` within the model
- Schema normalizer produces expected field capabilities
- Media metadata semantic validation passes
- Capability endpoint returns the new model/operation
- Submit rejects invalid inputs with field-level errors

## References

- [Registry schema, normalization rules, and media groups](references/registry-schema.md)
- [Fal schema sourcing and translation rules](references/fal-schema-translation.md)
- [Capability and submit API contracts, error codes](references/api-contract.md)
- [Architecture, components, runtime flow, and caching](references/architecture.md)
- [Testing — what to write and where](references/testing.md)