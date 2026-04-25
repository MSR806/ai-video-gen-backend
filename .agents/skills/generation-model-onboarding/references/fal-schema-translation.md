# Fal Schema Translation Reference

Fal is one of the supported providers. This reference covers how to source a Fal model's schema and translate it into the local registry format.

## Finding the Schema

Fal publishes an LLM-friendly schema page for every model endpoint at:

```
https://fal.ai/models/<endpoint_id>/llms.txt
```

The `endpoint_id` is the Fal path for that specific operation variant, for example:

| Operation | endpoint_id |
|-----------|-------------|
| Kling image-to-video | `fal-ai/kling-video/v2.6/pro/image-to-video` |
| Veo 3.1 first/last frame | `fal-ai/veo3.1/fast/first-last-frame-to-video` |

So the schema URL for Kling image-to-video would be:
```
https://fal.ai/models/fal-ai/kling-video/v2.6/pro/image-to-video/llms.txt
```

The `endpoint_id` also becomes the value of the `endpoint_id` field in the local registry operation entry.

## Reading the llms.txt Response

The `llms.txt` page describes the model in plain text with a JSON schema block for the request input. Look for the section that describes the **input** or **request** schema — it will list properties with their types, descriptions, defaults, and constraints.

Key things to extract:
- The list of properties and their types
- Which fields are required vs optional
- `description`, `default`, `enum`, `minimum`, `maximum` for each field
- Which fields accept image or video URLs (these are the media inputs)

## Translation Rules

### Types

| Fal type | Local type |
|----------|------------|
| `string` | `string` |
| `integer` | `integer` |
| `number` | `number` |
| `boolean` | `boolean` |
| `array of strings` | `array` with `items.type: string` |

### Nullable / optional fields

Fal schemas often mark fields as nullable or use union types like `string | null`. In the local registry:
- Drop the null variant — just use the base type
- Omit the field from the `required` array (making it optional)
- Keep the `default` value if one is provided

### URL / media fields

Any field that accepts an image URL, video URL, or media asset URL must have `"format": "uri"` added in the local registry. The frontend uses this to identify media inputs. Common Fal field names to watch for: `image_url`, `video_url`, `first_frame_url`, `last_frame_url`, `mask_url`, `lora_url`.

### Fields to preserve

Always carry these over from the Fal schema if present:
- `title`
- `description`
- `default`
- `enum`
- `minimum`
- `maximum`

### Fields to drop

- Fal-internal metadata fields not relevant to the input (e.g. output format hints, webhook config)
- Any field that controls provider-side behavior the frontend should never expose

### `additionalProperties`

Always add `"additionalProperties": false` at the root of `input_schema`. Fal schemas do not include this — it is a local registry constraint that causes the backend to reject unknown fields on submit.

## After Translation

Once the schema is translated:

1. Assign `x_ui_group: "advanced"` to fields that should not be shown by default (e.g. seed, guidance scale, num inference steps)
2. Identify the primary media inputs and set up `x_ui_media_groups` with the appropriate layout (`single`, `sequence`, or `gallery`) — see [registry-schema.md](registry-schema.md) for media group rules
3. Choose the correct `operation_type` for this operation — see the operation type vocabulary in [registry-schema.md](registry-schema.md)
