"""
S3 storage backend.

Implements :class:`~spec_registry.storage.StorageBackend` using ``boto3``.
Only imported when :func:`~spec_registry.storage.create_backend` encounters
an ``s3://`` URI, keeping ``boto3`` as a lazy dependency for local-only
usage.
"""

from __future__ import annotations

import boto3


class S3StorageBackend:
    """Storage backend backed by an S3 bucket."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        *,
        region_name: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        """Initialize with bucket name and optional prefix/region/endpoint."""
        self._client = boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
        )
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")

    def _full_key(self, key: str) -> str:
        if self._prefix:
            return f"{self._prefix}/{key}"
        return key

    def read(self, key: str) -> str | None:
        """Read the content stored at *key*, or ``None`` if it does not exist."""
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=self._full_key(key))
            return resp["Body"].read().decode("utf-8")
        except self._client.exceptions.NoSuchKey:
            return None

    def write(self, key: str, content: str) -> str:
        """Write *content* to *key* and return the S3 URI."""
        full_key = self._full_key(key)
        self._client.put_object(
            Bucket=self._bucket,
            Key=full_key,
            Body=content.encode("utf-8"),
        )
        return f"s3://{self._bucket}/{full_key}"

    def delete(self, key: str) -> None:
        """Delete the object at *key*.  No error if it does not exist."""
        self._client.delete_object(Bucket=self._bucket, Key=self._full_key(key))

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return keys whose names start with *prefix*."""
        full_prefix = self._full_key(prefix)
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                raw_key: str = obj["Key"]
                # Strip the configured prefix to return relative keys
                if self._prefix:
                    raw_key = raw_key[len(self._prefix) + 1 :]
                keys.append(raw_key)
        return sorted(keys)

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._full_key(key))
        except self._client.exceptions.ClientError:
            return False
        return True
