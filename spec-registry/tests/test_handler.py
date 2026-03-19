"""Tests for the handler module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from spec_registry.handler import handler

from .conftest import ACME_SWAGGER2_SPEC


def _make_s3_event(bucket: str, key: str) -> dict[str, Any]:
    """Build a minimal S3 event notification payload."""
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                },
            },
        ],
    }


class TestHandlerValidEvents:
    """Tests for handler with valid S3 events."""

    @patch("spec_registry.handler.S3StorageBackend")
    def test_handler_rebuilds_index(self, mock_backend_cls: MagicMock) -> None:
        """Handler rebuilds index on valid S3 event."""
        backend = MagicMock()
        mock_backend_cls.return_value = backend

        spec_content = json.dumps(ACME_SWAGGER2_SPEC)
        backend.list_keys.return_value = ["acme.json"]
        backend.read.return_value = spec_content

        event = _make_s3_event("my-bucket", "specs/acme.json")
        result = handler(event, None)

        assert result["statusCode"] == 200
        mock_backend_cls.assert_called_once_with(bucket="my-bucket", prefix="specs")
        backend.write.assert_called_once()
        written_key = backend.write.call_args[0][0]
        assert written_key == "spec_index.json"

    @patch("spec_registry.handler.S3StorageBackend")
    def test_handler_no_prefix(self, mock_backend_cls: MagicMock) -> None:
        """Handler handles keys without a prefix (root-level uploads)."""
        backend = MagicMock()
        mock_backend_cls.return_value = backend

        spec_content = json.dumps(ACME_SWAGGER2_SPEC)
        backend.list_keys.return_value = ["acme.json"]
        backend.read.return_value = spec_content

        event = _make_s3_event("my-bucket", "acme.json")
        result = handler(event, None)

        assert result["statusCode"] == 200
        mock_backend_cls.assert_called_once_with(bucket="my-bucket", prefix="")


class TestHandlerInvalidEvents:
    """Tests for handler with missing or malformed events."""

    def test_handler_no_records(self) -> None:
        """Handler returns 400 when there are no records."""
        result = handler({"Records": []}, None)
        assert result["statusCode"] == 400

    def test_handler_missing_bucket(self) -> None:
        """Handler returns 400 when bucket name is missing."""
        event: dict[str, Any] = {
            "Records": [
                {
                    "s3": {
                        "bucket": {},
                        "object": {"key": "specs/acme.json"},
                    },
                },
            ],
        }
        result = handler(event, None)
        assert result["statusCode"] == 400

    def test_handler_missing_key(self) -> None:
        """Handler returns 400 when object key is missing."""
        event: dict[str, Any] = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "my-bucket"},
                        "object": {},
                    },
                },
            ],
        }
        result = handler(event, None)
        assert result["statusCode"] == 400


class TestHandlerRebuildFailure:
    """Tests for handler when index rebuild fails."""

    @patch("spec_registry.handler.S3StorageBackend")
    def test_handler_rebuild_failure(self, mock_backend_cls: MagicMock) -> None:
        """Handler returns 500 when index rebuild raises an exception."""
        backend = MagicMock()
        mock_backend_cls.return_value = backend
        backend.list_keys.side_effect = RuntimeError("S3 unavailable")

        event = _make_s3_event("my-bucket", "specs/acme.json")
        result = handler(event, None)

        assert result["statusCode"] == 500
