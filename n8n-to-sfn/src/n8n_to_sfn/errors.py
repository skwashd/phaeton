"""
Custom exception hierarchy for the translation engine.

All translation engine exceptions inherit from ``TranslationError``.
"""

from __future__ import annotations


class TranslationError(Exception):
    """
    Base exception for all translation engine errors.

    Example::

        raise TranslationError("Something went wrong during translation")
    """


class ASLValidationError(TranslationError):
    """
    Raised when generated ASL fails schema validation.

    Example::

        raise ASLValidationError(
            "ASL validation failed",
            violations=["'StartAt' is a required property"],
        )
    """

    def __init__(self, message: str, violations: list[str] | None = None) -> None:
        """Initialize with a message and optional list of schema violations."""
        self.violations = violations or []
        super().__init__(message)


class UnsupportedNodeError(TranslationError):
    """
    Raised for n8n nodes the engine cannot translate.

    Example::

        raise UnsupportedNodeError("Node type 'n8n-nodes-base.ftp' is not supported")
    """


class ExpressionTranslationError(TranslationError):
    """
    Raised when an n8n expression fails to translate to JSONata.

    Example::

        raise ExpressionTranslationError(
            "Cannot translate expression: {{ $json.complex() }}",
            expression="{{ $json.complex() }}",
        )
    """

    def __init__(self, message: str, expression: str = "") -> None:
        """Initialize with a message and the original expression."""
        self.expression = expression
        super().__init__(message)
