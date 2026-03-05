from __future__ import annotations

from collections.abc import Mapping

from ai_video_gen_backend.domain.generation import InputFieldCapability
from ai_video_gen_backend.domain.types import JsonObject, JsonValue

_SCALAR_FIELD_TYPES = {'string', 'integer', 'number', 'boolean', 'array', 'object'}


def normalize_operation_schema(
    input_schema: JsonObject,
) -> tuple[list[str], list[InputFieldCapability]]:
    required = _extract_required(input_schema)
    properties_raw = input_schema.get('properties')
    if not isinstance(properties_raw, dict):
        return required, []

    fields: list[InputFieldCapability] = []
    for key, field_schema_raw in properties_raw.items():
        if not isinstance(key, str) or not isinstance(field_schema_raw, Mapping):
            continue

        field_schema = _to_object(field_schema_raw)
        field_type = _resolve_field_type(field_schema)
        items_type = _resolve_items_type(field_schema)
        description = field_schema.get('description')
        format_value = field_schema.get('format')
        enum_value = _resolve_enum(field_schema.get('enum'))
        default_value = field_schema.get('default') if 'default' in field_schema else None

        fields.append(
            InputFieldCapability(
                key=key,
                type=field_type,
                required=key in required,
                description=description if isinstance(description, str) else None,
                default=default_value,
                enum=enum_value,
                format=format_value if isinstance(format_value, str) else None,
                items_type=items_type,
            )
        )

    return required, fields


def _extract_required(input_schema: JsonObject) -> list[str]:
    raw_required = input_schema.get('required')
    if not isinstance(raw_required, list):
        return []
    return [value for value in raw_required if isinstance(value, str)]


def _resolve_field_type(field_schema: JsonObject) -> str:
    any_of = field_schema.get('anyOf')
    if isinstance(any_of, list) and len(any_of) > 0:
        return 'union'

    raw_type = field_schema.get('type')
    if isinstance(raw_type, str):
        return raw_type if raw_type in _SCALAR_FIELD_TYPES else 'object'
    if isinstance(raw_type, list):
        return 'union' if len(raw_type) > 1 else _sanitize_field_type(raw_type)
    return 'object'


def _sanitize_field_type(raw_type: list[object]) -> str:
    for candidate in raw_type:
        if isinstance(candidate, str) and candidate in _SCALAR_FIELD_TYPES:
            return candidate
    return 'object'


def _resolve_items_type(field_schema: JsonObject) -> str | None:
    raw_type = field_schema.get('type')
    if raw_type != 'array':
        return None

    items = field_schema.get('items')
    if not isinstance(items, Mapping):
        return None

    item_type = items.get('type')
    if isinstance(item_type, str):
        return item_type
    if isinstance(item_type, list):
        return 'union'
    return None


def _resolve_enum(raw_enum: object) -> list[JsonValue] | None:
    if not isinstance(raw_enum, list):
        return None
    return list(raw_enum)


def _to_object(value: Mapping[object, object]) -> JsonObject:
    result: JsonObject = {}
    for key, item in value.items():
        if isinstance(key, str):
            result[key] = item
    return result
