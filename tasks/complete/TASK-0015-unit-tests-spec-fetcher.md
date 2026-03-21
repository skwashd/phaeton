# Unit Tests Spec Fetcher

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #15

## Overview

The `SpecFetcher` class (created in TASK-0003) downloads API spec files from S3 to a local cache directory. These tests verify S3 download behavior, caching logic, and error handling using mocked `boto3` clients — no real AWS calls.

## Dependencies

- **Blocked by:** TASK-0003 (SpecFetcher must exist)
- **Blocks:** None

## Acceptance Criteria

1. `test_fetch_downloads_from_s3` passes — verifies `s3_client.download_file` is called with correct `bucket`, `key` (prefix + filename), and local path.
2. `test_fetch_uses_cache` passes — second call for the same file returns cached path without calling S3 again.
3. `test_fetch_handles_s3_error` passes — raises appropriate error when S3 download fails.
4. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
5. `uv run pytest tests/test_spec_fetcher.py` passes in `n8n-to-sfn/`.
6. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/tests/test_spec_fetcher.py` (new)

### Technical Approach

1. Import and set up mocks:
   ```python
   from unittest.mock import MagicMock, patch
   from n8n_to_sfn.translators.spec_fetcher import SpecFetcher
   ```

2. `test_fetch_downloads_from_s3`:
   ```python
   @patch("n8n_to_sfn.translators.spec_fetcher.boto3", create=True)
   def test_fetch_downloads_from_s3(mock_boto3: MagicMock, tmp_path: Path) -> None:
       """Test that fetch downloads the spec file from S3."""
       mock_client = MagicMock()
       mock_boto3.client.return_value = mock_client
       # Make download_file actually create the file
       def side_effect(bucket: str, key: str, filename: str) -> None:
           Path(filename).write_text("{}")
       mock_client.download_file.side_effect = side_effect

       fetcher = SpecFetcher(bucket="my-bucket", prefix="specs/", cache_dir=str(tmp_path))
       result = fetcher.fetch("slack.json")

       mock_client.download_file.assert_called_once_with("my-bucket", "specs/slack.json", str(tmp_path / "slack.json"))
       assert result == tmp_path / "slack.json"
   ```

3. `test_fetch_uses_cache`:
   - Create the file manually in `tmp_path` before calling `fetch()`
   - Assert `download_file` is NOT called
   - Assert the returned path matches the pre-existing file

4. `test_fetch_handles_s3_error`:
   - Make `download_file` raise `botocore.exceptions.ClientError` (or the wrapped `RuntimeError`)
   - Assert the appropriate exception is raised with an informative message

### Testing Requirements

- All S3 interactions are mocked — no AWS credentials needed.
- Use `tmp_path` fixture for the cache directory.
- Follow project conventions: `-> None` return annotations, docstrings on all test functions.
