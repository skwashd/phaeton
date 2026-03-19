"""
Lambda handler for spec registry index rebuilds.

Triggered by S3 ``s3:ObjectCreated`` events when a spec file is uploaded.
Rebuilds the full spec index from all spec files in the bucket.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from spec_registry.indexer import (
    _detect_auth_type,
    _extract_base_urls_openapi3,
    _extract_base_urls_swagger2,
    extract_resource_operations_from_spec,
    save_index_to_backend,
)
from spec_registry.storage_s3 import S3StorageBackend

logger = logging.getLogger(__name__)

# Only spec files with these extensions are indexed.
_SPEC_EXTENSIONS = (".json", ".yaml", ".yml")

# The key where the index is persisted within the same bucket/prefix.
_INDEX_KEY = "spec_index.json"


def _parse_spec_content(content: str, filename: str) -> dict[str, Any] | None:
    """Parse a spec file as JSON or YAML and return the dict, or ``None``."""
    lower = filename.lower()
    if lower.endswith(".json"):
        parsed = json.loads(content)
    else:
        import yaml

        parsed = yaml.safe_load(content)

    if isinstance(parsed, dict):
        return parsed
    return None


def _build_index_from_backend(backend: S3StorageBackend) -> None:
    """Read all spec files from the backend and rebuild the index."""
    from datetime import UTC, datetime

    from phaeton_models.spec import ApiSpecEntry, ApiSpecIndex

    keys = backend.list_keys()
    entries: list[ApiSpecEntry] = []

    for key in keys:
        if key == _INDEX_KEY:
            continue
        if not any(key.lower().endswith(ext) for ext in _SPEC_EXTENSIONS):
            continue

        content = backend.read(key)
        if content is None:
            logger.warning("Spec file %s listed but could not be read", key)
            continue

        spec = _parse_spec_content(content, key)
        if spec is None:
            logger.warning("Spec file %s could not be parsed", key)
            continue

        # Detect format
        if "swagger" in spec and str(spec["swagger"]).startswith("2."):
            spec_format = "swagger2"
            base_urls = _extract_base_urls_swagger2(spec)
        else:
            spec_format = "openapi3"
            base_urls = _extract_base_urls_openapi3(spec)

        info = spec.get("info", {})
        service_name = info.get("title", "") if isinstance(info, dict) else ""
        if not service_name:
            service_name = key.rsplit(".", maxsplit=1)[0]

        entries.append(
            ApiSpecEntry(
                spec_filename=key,
                service_name=service_name,
                base_urls=base_urls,
                auth_type=_detect_auth_type(spec),
                spec_format=spec_format,
                endpoints=extract_resource_operations_from_spec(spec),
            )
        )

    index = ApiSpecIndex(
        entries=entries,
        index_timestamp=datetime.now(tz=UTC),
    )
    save_index_to_backend(index, backend, key=_INDEX_KEY)
    logger.info("Rebuilt spec index with %d entries", len(entries))


def handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """
    AWS Lambda entry point for S3 event-driven index rebuilds.

    Expects an S3 event notification with at least one record containing
    ``s3.bucket.name`` and ``s3.object.key``.
    """
    records = event.get("Records", [])
    if not records:
        logger.error("No records in event")
        return {"statusCode": 400, "body": "No records in event"}

    record = records[0]
    s3_info = record.get("s3", {})
    bucket = s3_info.get("bucket", {}).get("name")
    key = s3_info.get("object", {}).get("key")

    if not bucket:
        logger.error("Missing bucket name in S3 event")
        return {"statusCode": 400, "body": "Missing bucket name"}
    if not key:
        logger.error("Missing object key in S3 event")
        return {"statusCode": 400, "body": "Missing object key"}

    logger.info("Spec file uploaded: s3://%s/%s", bucket, key)

    # Determine prefix: everything before the last path segment
    parts = key.rsplit("/", maxsplit=1)
    prefix = parts[0] if len(parts) > 1 else ""

    backend = S3StorageBackend(bucket=bucket, prefix=prefix)

    try:
        _build_index_from_backend(backend)
    except Exception:
        logger.exception("Failed to rebuild spec index")
        return {"statusCode": 500, "body": "Index rebuild failed"}

    return {"statusCode": 200, "body": "Index rebuilt successfully"}
