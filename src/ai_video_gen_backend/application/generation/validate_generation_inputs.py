from __future__ import annotations

import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ai_video_gen_backend.domain.types import JsonObject

_REQUIRED_PROPERTY_PATTERN = re.compile(r"^'(?P<name>[^']+)' is a required property$")


class InvalidGenerationInputsError(Exception):
    def __init__(self, errors: list[dict[str, object]]) -> None:
        super().__init__('Generation inputs validation failed')
        self.errors = errors


class GenerationInputValidator:
    def validate(self, *, inputs: JsonObject, schema: JsonObject) -> None:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(inputs), key=_sort_key)
        if len(errors) == 0:
            return

        mapped_errors = [_map_error(error) for error in errors]
        raise InvalidGenerationInputsError(mapped_errors)


def _sort_key(error: ValidationError) -> tuple[str, str]:
    path = '/'.join(str(part) for part in error.absolute_path)
    return path, error.message


def _map_error(error: ValidationError) -> dict[str, object]:
    location: list[object] = ['body', 'inputs', *list(error.absolute_path)]
    required_match = _REQUIRED_PROPERTY_PATTERN.match(error.message)
    if required_match is not None:
        location.append(required_match.group('name'))

    return {
        'loc': location,
        'msg': error.message,
    }
