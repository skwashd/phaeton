# Create Spec Registry Component

**Priority:** P0
**Effort:** L
**Gap Analysis Ref:** Item #6

## Overview

Spec file management (API specification indexing and node-to-spec matching) is currently embedded in `n8n-release-parser/`. This couples spec lifecycle to the n8n release parsing lifecycle, when in reality the API spec registry should be a standalone service that can grow independently of which nodes n8n supports.

The new `spec-registry/` component is a standalone indexed registry of API specifications. It owns: the S3 bucket for spec files, index building logic (parsing OpenAPI/Swagger specs into a searchable index), and spec-to-node matching. Spec files are named to map to n8n node names (e.g., `n8n-nodes-base.Slack.json`), which is the contract between the registry and consumers.

The component is event-driven: when a spec file is uploaded to S3, an `s3:ObjectCreated` event triggers the Lambda to rebuild the index. Uploaders don't need to know about the index — they just put files in the bucket.

## Dependencies

- **Blocked by:** TASK-0002 (spec models must be in phaeton-models first)
- **Blocks:** TASK-0007 (release-parser cleanup depends on spec-registry existing), TASK-0016 (deployment stack)

## Acceptance Criteria

1. `spec-registry/` directory exists with a complete Python package structure.
2. `indexer.py` can parse OpenAPI/Swagger spec files and build an `ApiSpecIndex`.
3. `matcher.py` can match n8n node types to spec entries using the naming convention.
4. `handler.py` implements a Lambda handler triggered by S3 events that rebuilds the index.
5. `storage.py` defines a `StorageBackend` protocol; `storage_s3.py` implements it for S3.
6. `cli.py` provides dev-only CLI commands for building index and matching locally.
7. `scripts/upload-spec.sh` provides a helper for uploading spec files with correct naming.
8. All spec models are imported from `phaeton_models.spec`, not defined locally.
9. Typer is a `dev` dependency.
10. `uv run pytest` passes in `spec-registry/`.
11. `uv run ruff check` passes in `spec-registry/`.
12. `uv run ty check` passes in `spec-registry/`.

## Implementation Details

### Files to Modify

- `spec-registry/pyproject.toml` (new)
- `spec-registry/src/spec_registry/__init__.py` (new)
- `spec-registry/src/spec_registry/indexer.py` (new)
- `spec-registry/src/spec_registry/matcher.py` (new)
- `spec-registry/src/spec_registry/handler.py` (new)
- `spec-registry/src/spec_registry/cli.py` (new)
- `spec-registry/src/spec_registry/storage.py` (new)
- `spec-registry/src/spec_registry/storage_s3.py` (new)
- `spec-registry/scripts/upload-spec.sh` (new)
- `spec-registry/tests/__init__.py` (new)
- `spec-registry/tests/conftest.py` (new)
- `spec-registry/tests/test_indexer.py` (new)
- `spec-registry/tests/test_matcher.py` (new)
- `spec-registry/tests/test_handler.py` (new)

### Technical Approach

1. **Read source material** from `n8n-release-parser/`:
   - `n8n-release-parser/src/n8n_release_parser/spec_index.py`: Contains `build_spec_index()`, `normalize_base_url()`, auth detection, endpoint extraction, `save_index()`, `load_index()`.
   - `n8n-release-parser/src/n8n_release_parser/matcher.py`: Contains `match_all_nodes()`.
   - `n8n-release-parser/src/n8n_release_parser/storage.py`: Contains `StorageBackend` protocol.
   - `n8n-release-parser/src/n8n_release_parser/storage_s3.py`: Contains S3 implementation.

2. **Create `pyproject.toml`** with dependencies:
   - `phaeton-models` for spec models (`ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, `NodeApiMapping`)
   - `pydantic` for any internal models
   - `boto3` for S3 access
   - `pyyaml` for YAML spec file parsing
   - `typer` in `[dependency-groups] dev`
   - Build system: `uv_build`

3. **Create `storage.py`** with the `StorageBackend` protocol (copy from release-parser — it's generic):
   ```python
   class StorageBackend(Protocol):
       def read(self, key: str) -> str: ...
       def write(self, key: str, content: str) -> None: ...
       def list_keys(self, prefix: str) -> list[str]: ...
   ```

4. **Create `storage_s3.py`** with the S3 implementation (copy from release-parser).

5. **Create `indexer.py`** from `spec_index.py`:
   - Move `build_spec_index()`, `normalize_base_url()`, auth detection helpers, endpoint extraction, `save_index()`, `load_index()`.
   - Import spec models from `phaeton_models.spec`.
   - Accept a `StorageBackend` for reading spec files and writing the index.

6. **Create `matcher.py`** from `matcher.py`:
   - Move `match_all_nodes()` and supporting functions.
   - Import spec models from `phaeton_models.spec`.

7. **Create `handler.py`**:
   - Lambda handler triggered by S3 event notifications.
   - Parse S3 event to get bucket and key of the uploaded spec file.
   - Instantiate `S3StorageBackend`, call `build_spec_index()` to rebuild the full index, save it.
   - Return success/failure response.

8. **Create `cli.py`** with Typer commands:
   - `build-index`: Build spec index from local directory (for dev/testing).
   - `match`: Match nodes against the index (for dev/testing).

9. **Create `scripts/upload-spec.sh`**:
   ```bash
   #!/usr/bin/env bash
   # Upload an API spec file to the spec registry S3 bucket
   # Usage: ./upload-spec.sh <local-file> <n8n-node-name> [bucket] [prefix]
   ```

### Testing Requirements

- `test_indexer.py`: Test `build_spec_index()` with sample OpenAPI specs. Test `normalize_base_url()`. Test auth detection. Test endpoint extraction. Test save/load round-trip using a mock storage backend.
- `test_matcher.py`: Test `match_all_nodes()` with known node types and spec index. Test no-match case. Test partial match.
- `test_handler.py`: Test handler with mock S3 event. Test missing bucket/key. Test index rebuild failure.
- Copy and adapt relevant tests from `n8n-release-parser/tests/test_spec_index.py` and `n8n-release-parser/tests/test_matcher.py`.
