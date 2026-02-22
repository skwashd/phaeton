"""Shared test fixtures for the n8n-to-sfn test suite."""

import json
from pathlib import Path

import pytest

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def asl_schema() -> dict:
    """Load the ASL JSON schema for validation tests."""
    schema_path = SCHEMAS_DIR / "asl_schema.json"
    with open(schema_path) as f:
        return json.load(f)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR
