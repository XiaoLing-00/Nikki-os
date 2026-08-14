from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator

from animation.action_mapper import ALLOWED_ACTIONS, ALLOWED_EMOTIONS

RESPONSE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["context", "response", "memory_update"],
    "additionalProperties": False,
    "properties": {
        "context": {"type": "object"},
        "response": {
            "type": "object",
            "required": ["text", "emotion", "action"],
            "additionalProperties": False,
            "properties": {
                "text": {"type": "string", "minLength": 1, "maxLength": 160},
                "emotion": {"type": "string", "enum": sorted(ALLOWED_EMOTIONS)},
                "action": {"type": "string", "enum": sorted(ALLOWED_ACTIONS)},
            },
        },
        "memory_update": {
            "type": "object",
            "required": ["key_info", "sentiment"],
            "additionalProperties": False,
            "properties": {
                "key_info": {"type": "string", "maxLength": 300},
                "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
            },
        },
    },
}

_VALIDATOR = Draft202012Validator(RESPONSE_SCHEMA)


class ResponseContractError(ValueError):
    pass


def validate_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ResponseContractError("model response must be a JSON object")
    errors = sorted(_VALIDATOR.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:5]
        )
        raise ResponseContractError(details)
    normalized = deepcopy(payload)
    normalized["response"]["text"] = normalized["response"]["text"].strip()[:160]
    normalized["memory_update"]["key_info"] = normalized["memory_update"]["key_info"].strip()[:300]
    return normalized
