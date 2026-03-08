from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from ai_video_gen_backend.domain.generation import (
    CapabilityRegistryError,
    InputFieldCapability,
    MediaGroupCapability,
)
from ai_video_gen_backend.domain.generation.capabilities import (
    MediaGroupLayout,
    MediaGroupPlacement,
)
from ai_video_gen_backend.domain.types import JsonObject, JsonValue

_SCALAR_FIELD_TYPES = {'string', 'integer', 'number', 'boolean', 'array', 'object'}
_MEDIA_LAYOUTS = {'single', 'sequence', 'gallery'}
_MEDIA_PLACEMENTS = {'top'}


def normalize_operation_schema(
    input_schema: JsonObject,
) -> tuple[list[str], list[InputFieldCapability], list[MediaGroupCapability]]:
    required = _extract_required(input_schema)
    media_groups = _resolve_media_groups(input_schema)
    properties_raw = input_schema.get('properties')
    if not isinstance(properties_raw, dict):
        _validate_media_metadata(fields=[], field_schemas={}, media_groups=media_groups)
        return required, [], media_groups

    fields: list[InputFieldCapability] = []
    field_schemas: dict[str, JsonObject] = {}
    for key, field_schema_raw in properties_raw.items():
        if not isinstance(key, str) or not isinstance(field_schema_raw, Mapping):
            continue

        field_schema = _to_object(field_schema_raw)
        field_schemas[key] = field_schema
        field_type = _resolve_field_type(field_schema)
        items_type = _resolve_items_type(field_schema)
        ui_group = field_schema.get('x_ui_group')
        title = field_schema.get('title')
        description = field_schema.get('description')
        format_value = field_schema.get('format')
        enum_value = _resolve_enum(field_schema.get('enum'))
        default_value = field_schema.get('default') if 'default' in field_schema else None
        minimum_value = _resolve_bound(field_schema.get('minimum'))
        maximum_value = _resolve_bound(field_schema.get('maximum'))
        media_group = field_schema.get('x_ui_media_group')
        media_order = _resolve_media_order(field_schema.get('x_ui_media_order'))
        media_name = field_schema.get('x_ui_media_name')

        fields.append(
            InputFieldCapability(
                key=key,
                type=field_type,
                required=key in required,
                ui_group=ui_group if isinstance(ui_group, str) else None,
                title=title if isinstance(title, str) else None,
                description=description if isinstance(description, str) else None,
                default=default_value,
                enum=enum_value,
                format=format_value if isinstance(format_value, str) else None,
                items_type=items_type,
                minimum=minimum_value,
                maximum=maximum_value,
                media_group=media_group if isinstance(media_group, str) else None,
                media_order=media_order,
                media_name=media_name if isinstance(media_name, str) else None,
            )
        )

    _validate_media_metadata(fields=fields, field_schemas=field_schemas, media_groups=media_groups)

    return required, fields, media_groups


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


def _resolve_bound(raw_bound: object) -> JsonValue | None:
    if isinstance(raw_bound, bool):
        return None
    if isinstance(raw_bound, (int, float, str)):
        return raw_bound
    return None


def _resolve_media_order(raw_order: object) -> int | None:
    if isinstance(raw_order, bool):
        return None
    if isinstance(raw_order, int):
        return raw_order
    return None


def _resolve_media_groups(input_schema: JsonObject) -> list[MediaGroupCapability]:
    raw_groups = input_schema.get('x_ui_media_groups')
    if raw_groups is None:
        return []
    if not isinstance(raw_groups, list):
        raise CapabilityRegistryError('x_ui_media_groups must be a list')

    media_groups: list[MediaGroupCapability] = []
    seen_group_keys: set[str] = set()
    for index, raw_group in enumerate(raw_groups):
        if not isinstance(raw_group, Mapping):
            raise CapabilityRegistryError(f'x_ui_media_groups[{index}] must be an object')

        group = _to_object(raw_group)
        group_key = group.get('group_key')
        layout = group.get('layout')
        placement = group.get('placement')

        if not isinstance(group_key, str) or len(group_key.strip()) == 0:
            raise CapabilityRegistryError(
                f'x_ui_media_groups[{index}].group_key must be a non-empty string'
            )
        if group_key in seen_group_keys:
            raise CapabilityRegistryError(f'Duplicate x_ui_media_groups.group_key "{group_key}"')
        if layout not in _MEDIA_LAYOUTS:
            raise CapabilityRegistryError(
                f'x_ui_media_groups[{index}].layout must be one of {sorted(_MEDIA_LAYOUTS)}'
            )
        if placement not in _MEDIA_PLACEMENTS:
            raise CapabilityRegistryError(
                f'x_ui_media_groups[{index}].placement must be one of {sorted(_MEDIA_PLACEMENTS)}'
            )

        seen_group_keys.add(group_key)
        media_groups.append(
            MediaGroupCapability(
                group_key=group_key,
                layout=cast(MediaGroupLayout, layout),
                placement=cast(MediaGroupPlacement, placement),
            )
        )

    return media_groups


def _validate_media_metadata(
    *,
    fields: list[InputFieldCapability],
    field_schemas: dict[str, JsonObject],
    media_groups: list[MediaGroupCapability],
) -> None:
    if len(media_groups) == 0:
        for field in fields:
            if field.media_group is not None:
                raise CapabilityRegistryError(
                    f'Field "{field.key}" declares x_ui_media_group without x_ui_media_groups'
                )
            if field.media_order is not None:
                raise CapabilityRegistryError(
                    f'Field "{field.key}" declares x_ui_media_order without x_ui_media_group'
                )
            if field.media_name is not None and field.media_group is None:
                raise CapabilityRegistryError(
                    f'Field "{field.key}" declares x_ui_media_name without x_ui_media_group'
                )
        return

    groups_by_key = {group.group_key: group for group in media_groups}
    members_by_group: dict[str, list[InputFieldCapability]] = {
        group.group_key: [] for group in media_groups
    }

    for field in fields:
        if field.media_group is None:
            if field.media_order is not None:
                raise CapabilityRegistryError(
                    f'Field "{field.key}" declares x_ui_media_order without x_ui_media_group'
                )
            if field.media_name is not None:
                raise CapabilityRegistryError(
                    f'Field "{field.key}" declares x_ui_media_name without x_ui_media_group'
                )
            continue

        if field.media_group not in groups_by_key:
            raise CapabilityRegistryError(
                f'Field "{field.key}" references unknown x_ui_media_group "{field.media_group}"'
            )
        members_by_group[field.media_group].append(field)

    for group in media_groups:
        members = members_by_group[group.group_key]
        if len(members) == 0:
            raise CapabilityRegistryError(
                f'x_ui_media_group "{group.group_key}" does not have any member fields'
            )

        if group.layout == 'single':
            if len(members) != 1:
                raise CapabilityRegistryError(
                    f'x_ui_media_group "{group.group_key}" with layout "single" '
                    'must have exactly one field'
                )
            if not _is_uri_string_field(members[0]):
                raise CapabilityRegistryError(
                    f'Field "{members[0].key}" is invalid for '
                    f'x_ui_media_group "{group.group_key}" layout "single"'
                )
            continue

        if group.layout == 'gallery':
            if len(members) != 1:
                raise CapabilityRegistryError(
                    f'x_ui_media_group "{group.group_key}" with layout "gallery" '
                    'must have exactly one field'
                )
            if not _is_uri_array_field(members[0], field_schemas.get(members[0].key, {})):
                raise CapabilityRegistryError(
                    f'Field "{members[0].key}" is invalid for '
                    f'x_ui_media_group "{group.group_key}" layout "gallery"'
                )
            continue

        orders: set[int] = set()
        for field in members:
            if not _is_uri_string_field(field):
                raise CapabilityRegistryError(
                    f'Field "{field.key}" is invalid for '
                    f'x_ui_media_group "{group.group_key}" layout "sequence"'
                )
            if field.media_order is None:
                raise CapabilityRegistryError(
                    f'Field "{field.key}" in x_ui_media_group "{group.group_key}" '
                    'layout "sequence" must define x_ui_media_order'
                )
            if field.media_order in orders:
                raise CapabilityRegistryError(
                    f'Duplicate x_ui_media_order {field.media_order} in '
                    f'x_ui_media_group "{group.group_key}"'
                )
            orders.add(field.media_order)


def _is_uri_string_field(field: InputFieldCapability) -> bool:
    return field.type == 'string' and field.format == 'uri'


def _is_uri_array_field(field: InputFieldCapability, field_schema: JsonObject) -> bool:
    if field.type != 'array' or field.items_type != 'string':
        return False

    items = field_schema.get('items')
    if not isinstance(items, Mapping):
        return False

    item_format = items.get('format')
    return isinstance(item_format, str) and item_format == 'uri'


def _to_object(value: Mapping[object, object]) -> JsonObject:
    result: JsonObject = {}
    for key, item in value.items():
        if isinstance(key, str):
            result[key] = item
    return result
