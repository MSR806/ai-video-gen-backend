# Registry Schema Reference

## Model File Shape

One JSON file per model under `model_registry/`. Each file defines exactly one product-visible model.

Required model-level fields:


| Field          | Notes                           |
| -------------- | ------------------------------- |
| `sort_order`   | Integer; controls display order |
| `model_key`    | Unique across all models        |
| `display_name` | User-facing label               |
| `provider`     | Always `"fal"` currently        |
| `media_type`   | `"image"` or `"video"`          |
| `enabled`      | `true` / `false`                |
| `operations`   | Non-empty array                 |


Required operation-level fields:

| Field            | Notes |
|------------------|-------|
| `operation_key`  | Unique within the model file — used by the backend to resolve and submit the operation |
| `operation_type` | Semantic category — used by the frontend to select a rendering pattern |
| `operation_name` | User-facing label shown in the UI |
| `endpoint_id`    | Provider endpoint path |
| `input_schema`   | JSON schema object (see below) |

### The three operation identifiers

These serve distinct purposes and must not be conflated:

- **`operation_key`** — stable backend handle. Must be unique within a model file. Used in `POST /generate` requests and persisted on generation runs. Example: `text_to_video_fast`
- **`operation_type`** — semantic category. Tells the frontend which rendering pattern to use. Multiple operations on the same model can share an `operation_type` as long as their `operation_key` values differ. Example: both `text_to_video` and `text_to_video_fast` can carry `operation_type: "text_to_video"`
- **`operation_name`** — display label only. No uniqueness constraint. Example: `"Text to Video (Fast)"`

### Known operation_type values

| `operation_type` | Meaning |
|------------------|---------|
| `text_to_video` | Generate video from a text prompt |
| `image_to_video` | Animate a single image into a video |
| `first_last_frame_to_video` | Generate video interpolated between a start and end frame |

Reuse an existing `operation_type` if the new operation fits one of the above patterns. Introducing a new `operation_type` requires a frontend code change to add a matching rendering pattern.

## Input Schema Normalization Rules

All `input_schema` values must be strict JSON Schema objects:

- `"type": "object"` at the root
- `"additionalProperties": false` — unknown fields are rejected on submit
- List all required fields in `"required"`
- Preserve from the provider schema: `title`, `description`, `default`, `enum`, `minimum`, `maximum`
- Flatten nullable provider fields into optional local fields (omit from `required`)
- Add `"format": "uri"` to all URL/image/video fields — the frontend uses this to treat them as media inputs

## UI Metadata Extensions

### Field grouping

`x_ui_group: "advanced"` on a property hides it from the default form view.

### Media groups

Root-level declaration on `input_schema`:

```json
"x_ui_media_groups": [
  { "group_key": "frames", "layout": "sequence", "placement": "top" }
]
```

Supported layouts:


| Layout     | Field constraint                                                  |
| ---------- | ----------------------------------------------------------------- |
| `single`   | Exactly one `format: uri` string field                            |
| `sequence` | `format: uri` string fields with unique `x_ui_media_order` values |
| `gallery`  | Exactly one array field whose items are `format: uri` strings     |


Supported placement: `"top"` only.

Field-level annotations for media group membership:

```json
"image_url": {
  "x_ui_media_group": "frames",
  "x_ui_media_order": 1,
  "x_ui_media_name": "Start",
  "type": "string",
  "format": "uri"
}
```

### Media metadata validation rules (enforced at load time)

- Every `x_ui_media_group` reference must point to a declared group in `x_ui_media_groups`
- Every declared group must have at least one member field
- `x_ui_media_order` and `x_ui_media_name` cannot appear without `x_ui_media_group`
- `single` groups must contain exactly one field
- `gallery` groups must contain exactly one array field
- `sequence` groups must have unique `x_ui_media_order` values across member fields

## Complete Example

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
          { "group_key": "frames", "layout": "sequence", "placement": "top" }
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
          },
          "num_frames": {
            "x_ui_group": "advanced",
            "type": "integer",
            "minimum": 1,
            "maximum": 300,
            "default": 129,
            "description": "Number of frames to generate."
          }
        },
        "additionalProperties": false
      }
    }
  ]
}
```

## Schema Normalization Output

The `schema_normalizer` converts each property into an `InputFieldCapability`:


| Output field  | Source                              |
| ------------- | ----------------------------------- |
| `key`         | property name                       |
| `type`        | `type`                              |
| `required`    | membership in root `required` array |
| `title`       | `title`                             |
| `description` | `description`                       |
| `default`     | `default`                           |
| `enum`        | `enum`                              |
| `format`      | `format`                            |
| `itemsType`   | `items.type` (for array fields)     |
| `minimum`     | `minimum`                           |
| `maximum`     | `maximum`                           |
| `uiGroup`     | `x_ui_group`                        |
| `mediaGroup`  | `x_ui_media_group`                  |
| `mediaOrder`  | `x_ui_media_order`                  |
| `mediaName`   | `x_ui_media_name`                   |


