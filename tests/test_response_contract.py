from __future__ import annotations

import pytest

from services.response_contract import ResponseContractError, validate_response

VALID = {
    "context": {},
    "response": {"text": "今天也一起加油呀。", "emotion": "wink", "action": "motion_idle"},
    "memory_update": {"key_info": "", "sentiment": "neutral"},
}


def test_valid_response_contract_is_accepted() -> None:
    assert validate_response(VALID)["response"]["text"] == "今天也一起加油呀。"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {**VALID, "response": {**VALID["response"], "action": "shell_exec"}},
        {**VALID, "extra": "not allowed"},
        {**VALID, "response": {**VALID["response"], "text": "x" * 161}},
    ],
)
def test_invalid_response_contract_is_rejected(payload: dict) -> None:
    with pytest.raises(ResponseContractError):
        validate_response(payload)
