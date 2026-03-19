# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview and architecture.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/spec_registry/`
- **Lambda handler:** `spec_registry.handler:handler`
- **Dev CLI entry point:** `spec_registry.cli:app` (Typer — dev/testing only, not deployed)

## Component purpose

Standalone indexed registry of API specifications with S3-backed storage and event-driven index rebuilds. Parses Swagger 2.0 and OpenAPI 3.x specs, extracts endpoints, detects auth types, and matches n8n node types to API spec entries.

## Key modules

- `handler.py` — Lambda entry point. Triggered by S3 `ObjectCreated` events; rebuilds the full spec index from all spec files in the bucket.
- `indexer.py` — Builds searchable index from API specs. Handles Swagger 2.0 and OpenAPI 3.x formats. Provides `build_spec_index()`, `save_index()`, and `load_index()`.
- `matcher.py` — Matches n8n node types to API spec entries using filename convention and service name normalization. Provides `match_node_type()` and `match_all_nodes()`.
- `storage.py` — `StorageBackend` protocol and `LocalStorageBackend` implementation. Use `create_backend()` factory to instantiate.
- `storage_s3.py` — `S3StorageBackend` implementation using boto3.
- `cli.py` — Dev-only Typer CLI with `build_index` and `match` commands. Not bundled in Lambda deployments.

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`cli.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
- Storage backends implement the `StorageBackend` protocol in `storage.py`. Use `create_backend()` to instantiate.
- `boto3` is used directly (not lazy-imported) since S3 is the primary storage backend for this component.
