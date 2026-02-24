"""Tests for the storage module — LocalStorageBackend and create_backend factory."""

from __future__ import annotations

from pathlib import Path

from n8n_release_parser.storage import (
    LocalStorageBackend,
    StorageBackend,
    create_backend,
)


class TestLocalStorageBackend:
    def test_roundtrip(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        loc = backend.write("hello.json", '{"key": "value"}')
        assert loc.endswith("hello.json")

        content = backend.read("hello.json")
        assert content == '{"key": "value"}'

    def test_read_nonexistent_returns_none(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        assert backend.read("missing.json") is None

    def test_delete(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        backend.write("to_delete.json", "data")
        assert backend.exists("to_delete.json")

        backend.delete("to_delete.json")
        assert not backend.exists("to_delete.json")
        assert backend.read("to_delete.json") is None

    def test_delete_nonexistent_is_noop(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        backend.delete("nonexistent.json")  # should not raise

    def test_list_keys(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        backend.write("catalog_1_0_0.json", "{}")
        backend.write("catalog_2_0_0.json", "{}")
        backend.write("api_mappings.json", "{}")

        all_keys = backend.list_keys()
        assert len(all_keys) == 3

        catalog_keys = backend.list_keys("catalog_")
        assert catalog_keys == ["catalog_1_0_0.json", "catalog_2_0_0.json"]

    def test_exists(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        assert not backend.exists("nope.json")
        backend.write("yep.json", "data")
        assert backend.exists("yep.json")

    def test_satisfies_protocol(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(tmp_path / "store")
        assert isinstance(backend, StorageBackend)


class TestCreateBackend:
    def test_local_path(self, tmp_path: Path) -> None:
        backend = create_backend(str(tmp_path / "local"))
        assert isinstance(backend, LocalStorageBackend)

    def test_s3_uri(self) -> None:
        from n8n_release_parser.storage_s3 import S3StorageBackend

        backend = create_backend("s3://my-bucket/some/prefix")
        assert isinstance(backend, S3StorageBackend)
        assert backend._bucket == "my-bucket"
        assert backend._prefix == "some/prefix"

    def test_s3_uri_no_prefix(self) -> None:
        from n8n_release_parser.storage_s3 import S3StorageBackend

        backend = create_backend("s3://my-bucket")
        assert isinstance(backend, S3StorageBackend)
        assert backend._bucket == "my-bucket"
        assert backend._prefix == ""
