# CLAUDE.md

See [README.md](README.md) for project overview, architecture, and CLI usage.

## Quick reference

- **Language:** Python >= 3.14
- **Package manager:** uv
- **Build system:** Hatchling
- **Source layout:** `src/n8n_release_parser/`
- **Entry point:** `n8n_release_parser.cli:main`

## Commands

```bash
uv run pytest                        # run all tests
uv run pytest -m "not integration"   # skip integration tests
uv run ruff check --fix .            # lint
uv run ruff format .                 # format
uv run ty check                      # type check
uv run coverage run -m pytest && uv run coverage report -m  # coverage
```

## Code conventions

- All Pydantic models live in `models.py` and use `frozen=True` (immutable value objects).
- Modules use functional helpers (not classes) for parsing, diffing, and matching logic.
- `fetcher.py` uses async (`httpx`); the CLI wraps calls with `asyncio.run()`.
- Storage backends implement the `StorageBackend` protocol in `storage.py`. Use `create_backend()` to instantiate.
- `boto3` is lazy-imported only when `s3://` URIs are detected — do not add top-level boto3 imports elsewhere.

## Linting rules

Ruff is configured in `pyproject.toml` with an extensive rule set. Key points:

- Docstrings required on all public modules, classes, and functions (D rules).
- Type annotations required (ANN rules).
- Test files (`test_*`, `conftest.py`) are exempt from `S101` (assert), `S108` (tmp paths), and `D100-D104` (docstrings).
- Line length is not enforced (`E501` ignored).

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
  -> spec_index.py (models, storage)
  -> matcher.py    (models)
  -> priority.py   (models)
  -> cli.py        (all modules, lazy imports)
```

`cli.py` uses lazy imports within command functions to keep startup fast and avoid circular dependencies.
