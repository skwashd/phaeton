"""Unit tests for the SpecFetcher S3 download and caching logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from n8n_to_sfn.translators.spec_fetcher import SpecFetcher


@patch("boto3.client")
def test_fetch_downloads_from_s3(mock_boto3_client: MagicMock, tmp_path: Path) -> None:
    """Test that fetch downloads the spec file from S3."""
    mock_client = MagicMock()
    mock_boto3_client.return_value = mock_client

    def side_effect(bucket: str, key: str, filename: str) -> None:
        Path(filename).write_text("{}")

    mock_client.download_file.side_effect = side_effect

    fetcher = SpecFetcher(bucket="my-bucket", prefix="specs/", cache_dir=str(tmp_path))
    result = fetcher.fetch("slack.json")

    mock_client.download_file.assert_called_once_with(
        "my-bucket", "specs/slack.json", str(tmp_path / "slack.json")
    )
    assert result == tmp_path / "slack.json"


@patch("boto3.client")
def test_fetch_uses_cache(mock_boto3_client: MagicMock, tmp_path: Path) -> None:
    """Test that a cached file is returned without calling S3 again."""
    cached_file = tmp_path / "slack.json"
    cached_file.write_text("{}")

    fetcher = SpecFetcher(bucket="my-bucket", prefix="specs/", cache_dir=str(tmp_path))
    result = fetcher.fetch("slack.json")

    mock_boto3_client.assert_not_called()
    assert result == cached_file


@patch("boto3.client")
def test_fetch_handles_s3_error(mock_boto3_client: MagicMock, tmp_path: Path) -> None:
    """Test that an S3 download failure raises RuntimeError."""
    mock_client = MagicMock()
    mock_boto3_client.return_value = mock_client
    mock_client.download_file.side_effect = Exception("Access Denied")

    fetcher = SpecFetcher(bucket="my-bucket", prefix="specs/", cache_dir=str(tmp_path))

    with pytest.raises(RuntimeError, match=r"Failed to download spec 'slack\.json'"):
        fetcher.fetch("slack.json")
