"""Parser for n8n workflow JSON files."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from workflow_analyzer.models.exceptions import WorkflowParseError
from workflow_analyzer.models.n8n_workflow import N8nWorkflow


class WorkflowParser:
    """Loads and validates n8n workflow JSON into Pydantic models."""

    def parse_file(self, path: Path) -> N8nWorkflow:
        """Parse an n8n workflow from a JSON file path."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            msg = f"Failed to read workflow file: {path}"
            raise WorkflowParseError(msg, original_error=e) from e
        return self.parse_string(text)

    def parse_string(self, json_str: str) -> N8nWorkflow:
        """Parse an n8n workflow from a JSON string."""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON: {e}"
            raise WorkflowParseError(msg, original_error=e) from e
        return self.parse_dict(data)

    def parse_dict(self, data: dict[str, Any]) -> N8nWorkflow:
        """Parse an n8n workflow from a dictionary."""
        try:
            return N8nWorkflow.model_validate(data)
        except ValidationError as e:
            msg = f"Workflow validation failed: {e}"
            raise WorkflowParseError(msg, original_error=e) from e
