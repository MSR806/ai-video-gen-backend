# Testing Reference

When adding or updating a registry entry, these are the tests to write or update. Commit the registry file and tests together.

## Unit Tests

### Registry loader

- Registry file loads without errors
- All required model-level and operation-level fields are present
- Duplicate `operation_key` within the same model file is rejected
- Invalid registry files (missing required fields, wrong types) fail with a clear error

### Schema normalizer

- Each property in `input_schema` is normalized into the correct `InputFieldCapability` shape
- `required` membership is reflected correctly on each field
- `format: uri` fields have `format` surfaced in the capability output
- `x_ui_group` maps to `uiGroup`
- `x_ui_media_group`, `x_ui_media_order`, `x_ui_media_name` map to `mediaGroup`, `mediaOrder`, `mediaName`
- `items.type` for array fields maps to `itemsType`

### Media metadata validation

- Fields referencing an undeclared media group are rejected
- A declared group with no member fields is rejected
- `x_ui_media_order` or `x_ui_media_name` without `x_ui_media_group` is rejected
- `single` group with more than one field is rejected
- `gallery` group with a non-array field is rejected
- `sequence` group with duplicate `x_ui_media_order` values is rejected

### Operation resolution

- `model_key + operation_key` resolves to the correct Fal endpoint and schema
- Unknown `model_key` raises `unsupported_model_key`
- Unknown `operation_key` raises `unsupported_operation_key`

## API Tests

### Capability endpoint (`GET /api/v1/generation/capabilities`)

- New model appears in the correct `image` or `video` group
- Response includes `operationType`, `operationName`, `operationKey`, `endpointId`
- `fields` includes all expected `InputFieldCapability` entries
- `mediaGroups` reflects the declared media group layout
- URI fields have `format: "uri"` in the capability output
- `title`, `minimum`, `maximum` metadata is present where defined in the registry

### Submit endpoint (`POST /api/v1/collections/{id}/items/generate`)

- Valid inputs for the new operation are accepted
- Unknown fields in `inputs` are rejected with `schema_validation_failed`
- Missing required fields in `inputs` are rejected with field-level errors
