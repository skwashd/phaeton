# Create Spec Fetcher Module

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #3

## Overview

API spec files (OpenAPI 3.x / Swagger 2.0) are stored in S3 by the spec-registry component. The translator needs to download them to a local temp directory before PicoFun can parse them. Currently, no mechanism exists in `n8n-to-sfn` to fetch spec files from S3.

Create a `SpecFetcher` class that downloads spec files from a configured S3 bucket/prefix to a local cache directory. It lazy-imports `boto3` to avoid a hard dependency when running locally without AWS credentials. The fetcher caches files locally so repeated requests for the same spec don't re-download.

## Dependencies

- **Blocked by:** TASK-0001 (picofun dependency must be added first so the component resolves)
- **Blocks:** TASK-0006, TASK-0015

## Acceptance Criteria

1. A `SpecFetcher` class exists in `n8n-to-sfn/src/n8n_to_sfn/translators/spec_fetcher.py`.
2. `SpecFetcher.__init__` accepts `bucket: str`, `prefix: str = "specs/"`, and `cache_dir: str = ""` parameters.
3. `SpecFetcher.fetch(spec_filename)` downloads the file from `s3://{bucket}/{prefix}{spec_filename}` to `{cache_dir}/{spec_filename}` and returns the local `Path`.
4. If the file already exists in `cache_dir`, `fetch()` returns the cached path without calling S3.
5. `boto3` is lazy-imported (not at module top level) to avoid import errors when running without AWS SDK.
6. The class raises an informative error when S3 download fails (bucket not found, permission denied, network error).
7. All public methods and the class have type annotations and docstrings.
8. `uv run pytest` passes in `n8n-to-sfn/`.
9. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/spec_fetcher.py` (new)

### Technical Approach

1. Create `n8n-to-sfn/src/n8n_to_sfn/translators/spec_fetcher.py` with:

   ```python
   class SpecFetcher:
       def __init__(self, bucket: str, prefix: str = "specs/", cache_dir: str = "") -> None:
           """Initialize spec fetcher with S3 bucket config and local cache directory."""

       def fetch(self, spec_filename: str) -> Path:
           """Download spec to cache_dir if not cached. Return local path."""
   ```

2. In `fetch()`:
   - Construct the local path: `Path(self._cache_dir) / spec_filename`
   - If the file exists, return it immediately (cache hit)
   - Otherwise, lazy-import `boto3`, create an S3 client, and call `client.download_file(bucket, f"{prefix}{spec_filename}", str(local_path))`
   - Wrap S3 errors (e.g., `botocore.exceptions.ClientError`) in a descriptive `RuntimeError`
   - Ensure the cache directory exists (`Path.mkdir(parents=True, exist_ok=True)`)

3. Environment variables `PHAETON_SPEC_BUCKET` and `PHAETON_SPEC_PREFIX` are read by the handler (TASK-0007), not by this class. This class is configured via constructor parameters for testability.

### Testing Requirements

- `n8n-to-sfn/tests/test_spec_fetcher.py` (new, created in TASK-0015)
- Mock `boto3.client("s3")` using `unittest.mock.patch`
- Test cache hit (no S3 call on second fetch)
- Test S3 download with correct bucket/key
- Test error handling on S3 failure
