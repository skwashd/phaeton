"""Tests for the S3 storage backend using moto."""

from __future__ import annotations

from collections.abc import Generator

import boto3
import pytest
from moto import mock_aws

from n8n_release_parser.storage import StorageBackend
from n8n_release_parser.storage_s3 import S3StorageBackend

BUCKET = "test-bucket"
PREFIX = "catalogs"
REGION = "us-east-1"


@pytest.fixture
def s3_backend() -> Generator[S3StorageBackend]:
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(Bucket=BUCKET)
        yield S3StorageBackend(
            bucket=BUCKET,
            prefix=PREFIX,
            region_name=REGION,
        )


class TestS3StorageBackend:
    def test_roundtrip(self, s3_backend: S3StorageBackend) -> None:
        uri = s3_backend.write("hello.json", '{"key": "value"}')
        assert uri == f"s3://{BUCKET}/{PREFIX}/hello.json"

        content = s3_backend.read("hello.json")
        assert content == '{"key": "value"}'

    def test_read_nonexistent_returns_none(self, s3_backend: S3StorageBackend) -> None:
        assert s3_backend.read("missing.json") is None

    def test_delete(self, s3_backend: S3StorageBackend) -> None:
        s3_backend.write("to_delete.json", "data")
        assert s3_backend.exists("to_delete.json")

        s3_backend.delete("to_delete.json")
        assert not s3_backend.exists("to_delete.json")
        assert s3_backend.read("to_delete.json") is None

    def test_delete_nonexistent_is_noop(self, s3_backend: S3StorageBackend) -> None:
        s3_backend.delete("nonexistent.json")  # should not raise

    def test_list_keys(self, s3_backend: S3StorageBackend) -> None:
        s3_backend.write("catalog_1_0_0.json", "{}")
        s3_backend.write("catalog_2_0_0.json", "{}")
        s3_backend.write("api_mappings.json", "{}")

        all_keys = s3_backend.list_keys()
        assert len(all_keys) == 3

        catalog_keys = s3_backend.list_keys("catalog_")
        assert catalog_keys == ["catalog_1_0_0.json", "catalog_2_0_0.json"]

    def test_exists(self, s3_backend: S3StorageBackend) -> None:
        assert not s3_backend.exists("nope.json")
        s3_backend.write("yep.json", "data")
        assert s3_backend.exists("yep.json")

    def test_satisfies_protocol(self, s3_backend: S3StorageBackend) -> None:
        assert isinstance(s3_backend, StorageBackend)

    def test_no_prefix(self) -> None:
        with mock_aws():
            client = boto3.client("s3", region_name=REGION)
            client.create_bucket(Bucket=BUCKET)
            backend = S3StorageBackend(bucket=BUCKET, region_name=REGION)

            backend.write("root.json", "data")
            assert backend.read("root.json") == "data"
            assert backend.list_keys() == ["root.json"]
