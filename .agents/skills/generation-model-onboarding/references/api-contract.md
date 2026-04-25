# API Contract Reference

## Capability Endpoint

`GET /api/v1/generation/capabilities`

Response shape:

```json
{
  "image": [ /* ModelCapability */ ],
  "video": [ /* ModelCapability */ ]
}
```

### ModelCapability


| Field        | Type                        |
| ------------ | --------------------------- |
| `model`      | `str`                       |
| `modelKey`   | `str`                       |
| `provider`   | `str`                       |
| `operations` | `list[OperationCapability]` |


### OperationCapability


| Field           | Type                         |
| --------------- | ---------------------------- |
| `operationKey`  | `str`                        |
| `operationType` | `str`                        |
| `operationName` | `str`                        |
| `endpointId`    | `str`                        |
| `required`      | `list[str]`                  |
| `fields`        | `list[InputFieldCapability]` |
| `mediaGroups`   | `list[MediaGroupCapability]` |


### InputFieldCapability


| Field         | Type             |
| ------------- | ---------------- |
| `key`         | `str`            |
| `type`        | `str`            |
| `required`    | `bool`           |
| `uiGroup`     | `str             |
| `title`       | `str             |
| `description` | `str             |
| `default`     | `JsonValue       |
| `enum`        | `list[JsonValue] |
| `format`      | `str             |
| `itemsType`   | `str             |
| `minimum`     | `JsonValue       |
| `maximum`     | `JsonValue       |
| `mediaGroup`  | `str             |
| `mediaOrder`  | `int             |
| `mediaName`   | `str             |


### MediaGroupCapability


| Field       | Type      |
| ----------- | --------- |
| `groupKey`  | `str`     |
| `layout`    | `"single" |
| `placement` | `"top"`   |


## Submit Endpoint

`POST /api/v1/collections/{collection_id}/items/generate`

Request body:


| Field            | Type                   | Notes                                           |
| ---------------- | ---------------------- | ----------------------------------------------- |
| `projectId`      | `UUID`                 |                                                 |
| `modelKey`       | `str`                  | Must match a registry model                     |
| `operationKey`   | `str`                  | Must match an operation within that model       |
| `inputs`         | `dict[str, JsonValue]` | Validated against the resolved operation schema |
| `outputCount`    | `int`                  | Default `1`                                     |
| `idempotencyKey` | `str                   | null`                                           |


Response body:


| Field          | Type                                                      |
| -------------- | --------------------------------------------------------- |
| `runId`        | `UUID`                                                    |
| `status`       | `"QUEUED"                                                 |
| `modelKey`     | `str`                                                     |
| `operationKey` | `str`                                                     |
| `outputs`      | `list[{outputId, outputIndex, status, collectionItemId}]` |


## Error Codes


| Code                              | Cause                                       |
| --------------------------------- | ------------------------------------------- |
| `unsupported_model_key`           | `modelKey` not found in registry            |
| `unsupported_operation_key`       | `operationKey` not found under that model   |
| `capability_registry_load_failed` | Registry files failed to parse or validate  |
| `schema_validation_failed`        | `inputs` contains unknown or invalid fields |
| `provider_submit_failed`          | Fal returned an error                       |


Capability-loading failures are coarse at the API layer. The specific registry or normalization failure is in backend logs and tests.

## Observability

Log fields emitted on each generation submit:

- `model_key`
- `operation_key`
- `endpoint_id`
- `provider_request_id`
- validation failure summaries

## Security Rules

- Fal credentials must remain server-side only
- Never trust client-supplied schema information
- Validate all `inputs` against the resolved registry schema before submission
- Keep schemas strict (`additionalProperties: false`) and provider allowlists local

