# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview, architecture, and CLI usage.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/n8n_release_parser/`
- **Lambda handler:** `n8n_release_parser.handler:handler`
- **Dev CLI entry point:** `n8n_release_parser.cli:main` (Typer — dev/testing only, not deployed)

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`cli.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
- All Pydantic models live in `models.py` and use `frozen=True` (immutable value objects).
- Modules use functional helpers (not classes) for parsing and diffing logic.
- `fetcher.py` uses async (`httpx`); the CLI wraps calls with `asyncio.run()`.
- Storage backends implement the `StorageBackend` protocol in `storage.py`. Use `create_backend()` to instantiate.
- `boto3` is lazy-imported only when `s3://` URIs are detected — do not add top-level boto3 imports elsewhere.

## Test patterns

- Unit tests mirror source modules one-to-one (`test_parser.py` tests `parser.py`, etc.).
- Integration tests are in `tests/integration/` and marked with `@pytest.mark.integration`.
- HTTP mocking uses `respx`; S3 mocking uses `moto`.
- Async tests run automatically via `asyncio_mode = "auto"`.
- Fixtures are defined in `tests/conftest.py`.

## Module dependency order

When adding new functionality, be aware of the dependency flow:

```
models.py          (no internal deps)
  -> parser.py     (models)
  -> fetcher.py    (models)
  -> differ.py     (models)
  -> storage.py    (no internal deps)
  -> storage_s3.py (storage protocol)
  -> catalog.py    (models, storage)
  -> priority.py   (models)
  -> cli.py        (all modules, lazy imports)
```

`cli.py` uses lazy imports within command functions to keep startup fast and avoid circular dependencies.
