"""Custom exceptions for the workflow analyzer."""


class WorkflowParseError(Exception):
    """Raised when a workflow JSON file cannot be parsed or validated."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        """Initialize with a message and optional original error."""
        self.original_error = original_error
        super().__init__(message)
