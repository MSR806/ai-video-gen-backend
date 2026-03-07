from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ai_video_gen_backend.domain.generation import (
    CapabilityRegistryError,
    GenerationCapabilities,
    GenerationCapabilityRegistryPort,
    ModelCapability,
    OperationCapability,
    ResolvedGenerationOperation,
)
from ai_video_gen_backend.domain.types import JsonObject
from ai_video_gen_backend.infrastructure.providers.fal.schema_normalizer import (
    normalize_operation_schema,
)


@dataclass(frozen=True, slots=True)
class _RegistryOperation:
    operation_key: str
    endpoint_id: str
    input_schema: JsonObject


@dataclass(frozen=True, slots=True)
class _RegistryModel:
    model_key: str
    display_name: str
    provider: str
    media_type: str
    enabled: bool
    operations: list[_RegistryOperation]


@dataclass(frozen=True, slots=True)
class _RegistrySnapshot:
    loaded_at: float
    models: list[_RegistryModel]


class ModelRegistryLoader:
    def __init__(
        self,
        *,
        ttl_seconds: int,
        registry_path: Path | None = None,
        schema_path: Path | None = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parent
        self._registry_path = registry_path or (base_dir / 'model_registry.json')
        self._schema_path = schema_path or (base_dir / 'model_registry.schema.json')
        self._ttl_seconds = ttl_seconds
        self._cached: _RegistrySnapshot | None = None

    def load(self) -> list[_RegistryModel]:
        now = time.monotonic()
        if self._cached is not None and (now - self._cached.loaded_at) < self._ttl_seconds:
            return self._cached.models

        models = self._load_models_from_disk()
        self._cached = _RegistrySnapshot(loaded_at=now, models=models)
        return models

    def _load_models_from_disk(self) -> list[_RegistryModel]:
        try:
            schema_payload = json.loads(self._schema_path.read_text(encoding='utf-8'))
            registry_payload = json.loads(self._registry_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CapabilityRegistryError('Failed to read generation model registry') from exc

        if not isinstance(schema_payload, dict) or not isinstance(registry_payload, dict):
            raise CapabilityRegistryError('Invalid generation model registry payload')

        validator = Draft202012Validator(schema_payload)
        errors = sorted(validator.iter_errors(registry_payload), key=_error_sort_key)
        if len(errors) > 0:
            first = errors[0]
            path = '/'.join(str(part) for part in first.path)
            location = path if len(path) > 0 else '<root>'
            raise CapabilityRegistryError(
                f'Generation model registry validation failed at {location}: {first.message}'
            )

        models_raw = registry_payload.get('models')
        if not isinstance(models_raw, list):
            raise CapabilityRegistryError('Generation model registry missing models list')

        models: list[_RegistryModel] = []
        for model_raw in models_raw:
            if not isinstance(model_raw, dict):
                raise CapabilityRegistryError('Generation model entry must be an object')
            models.append(_parse_model(model_raw))

        return models


class FalGenerationModelRegistry(GenerationCapabilityRegistryPort):
    def __init__(self, loader: ModelRegistryLoader) -> None:
        self._loader = loader

    def list_capabilities(self) -> GenerationCapabilities:
        image_models: list[ModelCapability] = []
        video_models: list[ModelCapability] = []
        for model in self._enabled_models():
            operations: list[OperationCapability] = []
            for operation in model.operations:
                required, fields = normalize_operation_schema(operation.input_schema)
                operations.append(
                    OperationCapability(
                        operation_key=operation.operation_key,
                        endpoint_id=operation.endpoint_id,
                        required=required,
                        input_schema=dict(operation.input_schema),
                        fields=fields,
                    )
                )

            capability = ModelCapability(
                model=model.display_name,
                model_key=model.model_key,
                provider=model.provider,
                media_type='image' if model.media_type == 'image' else 'video',
                operations=operations,
            )
            if model.media_type == 'image':
                image_models.append(capability)
            else:
                video_models.append(capability)

        return GenerationCapabilities(image=image_models, video=video_models)

    def has_model(self, *, model_key: str) -> bool:
        return any(model.model_key == model_key for model in self._enabled_models())

    def resolve_operation(
        self, *, model_key: str, operation_key: str
    ) -> ResolvedGenerationOperation | None:
        for model in self._enabled_models():
            if model.model_key != model_key:
                continue
            for operation in model.operations:
                if operation.operation_key == operation_key:
                    return ResolvedGenerationOperation(
                        model_key=model.model_key,
                        model_display_name=model.display_name,
                        provider=model.provider,
                        media_type='image' if model.media_type == 'image' else 'video',
                        operation_key=operation.operation_key,
                        endpoint_id=operation.endpoint_id,
                        input_schema=dict(operation.input_schema),
                    )
            return None
        return None

    def _enabled_models(self) -> list[_RegistryModel]:
        return [model for model in self._loader.load() if model.enabled]


def _error_sort_key(error: ValidationError) -> tuple[str, str]:
    path = '/'.join(str(part) for part in error.absolute_path)
    return path, error.message


def _parse_model(model_raw: dict[str, object]) -> _RegistryModel:
    operations_raw = model_raw.get('operations')
    if not isinstance(operations_raw, list) or len(operations_raw) == 0:
        raise CapabilityRegistryError('Generation model operations must be a non-empty list')

    operations: list[_RegistryOperation] = []
    for operation_raw in operations_raw:
        if not isinstance(operation_raw, dict):
            raise CapabilityRegistryError('Generation operation entry must be an object')
        operations.append(_parse_operation(operation_raw))

    model_key = model_raw.get('model_key')
    display_name = model_raw.get('display_name')
    provider = model_raw.get('provider')
    media_type = model_raw.get('media_type')
    enabled = model_raw.get('enabled')

    if not isinstance(model_key, str) or len(model_key.strip()) == 0:
        raise CapabilityRegistryError('Generation model model_key must be a non-empty string')
    if not isinstance(display_name, str) or len(display_name.strip()) == 0:
        raise CapabilityRegistryError('Generation model display_name must be a non-empty string')
    if not isinstance(provider, str) or len(provider.strip()) == 0:
        raise CapabilityRegistryError('Generation model provider must be a non-empty string')
    if media_type == 'image':
        media_type_value = 'image'
    elif media_type == 'video':
        media_type_value = 'video'
    else:
        raise CapabilityRegistryError('Generation model media_type must be image or video')
    if not isinstance(enabled, bool):
        raise CapabilityRegistryError('Generation model enabled must be boolean')

    return _RegistryModel(
        model_key=model_key,
        display_name=display_name,
        provider=provider,
        media_type=media_type_value,
        enabled=enabled,
        operations=operations,
    )


def _parse_operation(operation_raw: dict[str, object]) -> _RegistryOperation:
    operation_key = operation_raw.get('operation_key')
    endpoint_id = operation_raw.get('endpoint_id')
    input_schema_raw = operation_raw.get('input_schema')

    if not isinstance(operation_key, str) or len(operation_key.strip()) == 0:
        raise CapabilityRegistryError(
            'Generation operation operation_key must be a non-empty string'
        )
    if not isinstance(endpoint_id, str) or len(endpoint_id.strip()) == 0:
        raise CapabilityRegistryError('Generation operation endpoint_id must be a non-empty string')
    if not isinstance(input_schema_raw, dict):
        raise CapabilityRegistryError('Generation operation input_schema must be an object')

    input_schema: JsonObject = {}
    for key, value in input_schema_raw.items():
        if isinstance(key, str):
            input_schema[key] = value

    return _RegistryOperation(
        operation_key=operation_key,
        endpoint_id=endpoint_id,
        input_schema=input_schema,
    )
