"""Spec fetcher module for downloading API spec files from S3."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class SpecFetcher:
    """
    Download API spec files from S3 with local caching.

    Fetches OpenAPI/Swagger spec files stored in S3 by the spec-registry
    component. Files are cached locally so repeated requests avoid
    redundant downloads. ``boto3`` is lazy-imported to avoid hard
    dependency when running without AWS credentials.
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "specs/",
        cache_dir: str = "",
    ) -> None:
        """
        Initialize spec fetcher with S3 bucket config and local cache directory.

        Args:
            bucket: S3 bucket name containing spec files.
            prefix: Key prefix within the bucket. Defaults to ``"specs/"``.
            cache_dir: Local directory for cached downloads. When empty a
                temporary directory is created automatically.

        """
        self._bucket = bucket
        self._prefix = prefix
        self._cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.mkdtemp())

    def fetch(self, spec_filename: str) -> Path:
        """
        Download spec to cache_dir if not already cached. Return local path.

        Args:
            spec_filename: Name of the spec file (e.g. ``"stripe.yaml"``).

        Returns:
            Local ``Path`` to the downloaded spec file.

        Raises:
            RuntimeError: If the S3 download fails for any reason.

        """
        local_path = self._cache_dir / spec_filename

        if local_path.exists():
            logger.debug("Cache hit for %s", spec_filename)
            return local_path

        self._cache_dir.mkdir(parents=True, exist_ok=True)

        s3_key = f"{self._prefix}{spec_filename}"
        logger.info("Downloading s3://%s/%s", self._bucket, s3_key)

        try:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client("s3")
            client.download_file(self._bucket, s3_key, str(local_path))
        except ClientError as exc:
            local_path.unlink(missing_ok=True)
            msg = (
                f"Failed to download spec '{spec_filename}' "
                f"from s3://{self._bucket}/{s3_key}: {exc}"
            )
            raise RuntimeError(msg) from exc
        except Exception as exc:
            local_path.unlink(missing_ok=True)
            msg = (
                f"Failed to download spec '{spec_filename}' "
                f"from s3://{self._bucket}/{s3_key}: {exc}"
            )
            raise RuntimeError(msg) from exc

        return local_path
