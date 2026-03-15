"""ASL definition writer and validator.

Validates ASL definitions against the JSON Schema and writes
``definition.asl.json`` to the output directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from n8n_to_sfn_packager.models.inputs import StateMachineDefinition


class ASLValidationError(Exception):
    """Raised when an ASL definition fails schema validation."""

    def __init__(self, errors: list[str]) -> None:
        """Initialise with the list of validation errors."""
        self.errors = errors
        super().__init__(
            f"ASL validation failed with {len(errors)} error(s): {'; '.join(errors)}"
        )


class ASLWriter:
    """Validates and writes ASL state-machine definitions."""

    def __init__(self, schema_path: Path | None = None) -> None:
        """Initialise with an optional custom schema path.

        Args:
            schema_path: Path to the ASL JSON Schema file.
                Defaults to ``docs/asl_schema.json`` relative to the monorepo root.

        """
        if schema_path is None:
            schema_path = (
                Path(__file__).resolve().parents[4] / "docs" / "asl_schema.json"
            )
        self._schema_path = schema_path
        self._schema: dict[str, Any] | None = None

    def _load_schema(self) -> dict[str, Any]:
        """Load and cache the ASL JSON Schema."""
        if self._schema is None:
            with self._schema_path.open() as f:
                self._schema = json.load(f)
        return self._schema

    def validate(self, definition: dict[str, Any]) -> list[str]:
        """Validate an ASL definition dict against the JSON Schema.

        Args:
            definition: The ASL definition to validate.

        Returns:
            A list of validation error messages (empty if valid).

        """
        schema = self._load_schema()
        validator_cls = jsonschema.validators.validator_for(schema)
        validator = validator_cls(schema)
        errors: list[str] = []
        for error in validator.iter_errors(definition):
            path = (
                ".".join(str(p) for p in error.absolute_path)
                if error.absolute_path
                else "<root>"
            )
            errors.append(f"{path}: {error.message}")
        return errors

    def write(self, definition: StateMachineDefinition, output_dir: Path) -> Path:
        """Write ``definition.asl.json`` to the output directory.

        Validates the ASL before writing. Raises ``ASLValidationError`` if
        the definition is invalid.

        Args:
            definition: The state-machine definition model.
            output_dir: Root output directory.

        Returns:
            Path to the written ``definition.asl.json`` file.

        """
        errors = self.validate(definition.asl)
        if errors:
            raise ASLValidationError(errors)

        statemachine_dir = output_dir / "statemachine"
        statemachine_dir.mkdir(parents=True, exist_ok=True)

        asl_path = statemachine_dir / "definition.asl.json"
        asl_path.write_text(json.dumps(definition.asl, indent=2, sort_keys=True) + "\n")
        return asl_path
