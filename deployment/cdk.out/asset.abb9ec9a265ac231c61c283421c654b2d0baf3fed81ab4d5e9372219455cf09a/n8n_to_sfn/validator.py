"""ASL validation against the JSON schema.

Validates generated ASL state machine JSON against ``schemas/asl_schema.json``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jsonschema

if TYPE_CHECKING:
    from n8n_to_sfn.models.asl import StateMachine


def _load_schema() -> dict[str, Any]:
    """Load the ASL JSON schema from disk."""
    schema_path = os.environ.get(
        "ASL_SCHEMA_PATH",
        str(Path(__file__).parent.parent.parent / "schemas" / "asl_schema.json"),
    )
    with open(schema_path) as f:
        return json.load(f)


_ASL_SCHEMA: dict[str, Any] = _load_schema()


def validate_asl(state_machine: StateMachine) -> list[str]:
    """Validate a StateMachine model against the ASL JSON schema.

    Returns a list of validation error messages (empty list means valid).
    """
    asl_json = state_machine.model_dump(by_alias=True)
    return validate_asl_json(asl_json)


def validate_asl_json(asl_json: dict[str, Any]) -> list[str]:
    """Validate a raw ASL dict against the ASL JSON schema.

    Returns a list of validation error messages (empty list means valid).
    """
    validator = jsonschema.Draft7Validator(_ASL_SCHEMA)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(asl_json), key=lambda e: list(e.path)):
        path = (
            ".".join(str(p) for p in error.absolute_path)
            if error.absolute_path
            else "(root)"
        )
        errors.append(f"{path}: {error.message}")
    return errors
