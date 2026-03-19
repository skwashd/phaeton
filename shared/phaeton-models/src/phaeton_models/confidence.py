"""Confidence level enum for AI agent translation responses."""

from enum import StrEnum


class Confidence(StrEnum):
    """Confidence level indicating translation quality."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
