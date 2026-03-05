from __future__ import annotations

import pytest

from ai_video_gen_backend.application.generation import (
    GenerationInputValidator,
    InvalidGenerationInputsError,
)
from ai_video_gen_backend.infrastructure.providers.fal.schema_normalizer import (
    normalize_operation_schema,
)


def test_schema_normalizer_extracts_required_and_field_shapes() -> None:
    input_schema = {
        'type': 'object',
        'required': ['prompt'],
        'properties': {
            'prompt': {'type': 'string', 'description': 'Main prompt'},
            'seed': {'type': 'integer', 'default': 42},
            'mode': {'type': 'string', 'enum': ['fast', 'quality']},
            'image_urls': {'type': 'array', 'items': {'type': 'string'}},
        },
        'additionalProperties': False,
    }

    required, fields = normalize_operation_schema(input_schema)

    assert required == ['prompt']
    assert len(fields) == 4
    prompt = next(field for field in fields if field.key == 'prompt')
    image_urls = next(field for field in fields if field.key == 'image_urls')
    assert prompt.required is True
    assert prompt.type == 'string'
    assert image_urls.type == 'array'
    assert image_urls.items_type == 'string'


def test_generation_input_validator_accepts_valid_payload() -> None:
    validator = GenerationInputValidator()
    schema = {
        'type': 'object',
        'required': ['prompt'],
        'properties': {
            'prompt': {'type': 'string'},
            'num_images': {'type': 'integer'},
        },
        'additionalProperties': False,
    }

    validator.validate(inputs={'prompt': 'hello', 'num_images': 1}, schema=schema)


def test_generation_input_validator_rejects_unknown_fields() -> None:
    validator = GenerationInputValidator()
    schema = {
        'type': 'object',
        'required': ['prompt'],
        'properties': {'prompt': {'type': 'string'}},
        'additionalProperties': False,
    }

    with pytest.raises(InvalidGenerationInputsError) as exc_info:
        validator.validate(
            inputs={'prompt': 'hello', 'unexpected': 'value'},
            schema=schema,
        )

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0]['loc'] == ['body', 'inputs']


def test_generation_input_validator_rejects_missing_required_field() -> None:
    validator = GenerationInputValidator()
    schema = {
        'type': 'object',
        'required': ['prompt'],
        'properties': {'prompt': {'type': 'string'}},
        'additionalProperties': False,
    }

    with pytest.raises(InvalidGenerationInputsError) as exc_info:
        validator.validate(inputs={}, schema=schema)

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0]['loc'] == ['body', 'inputs', 'prompt']
