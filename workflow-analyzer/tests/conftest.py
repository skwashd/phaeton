"""Shared pytest fixtures for workflow analyzer tests."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures/workflows directory."""
    return Path(__file__).parent / "fixtures" / "workflows"
