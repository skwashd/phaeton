# n8n Release Parser

Maintains a versioned catalog of n8n node types with API specification matching. Fetches `n8n-nodes-base` releases from npm, parses node descriptions into structured catalogs, diffs releases to track changes, and matches nodes against OpenAPI/Swagger specs to determine API coverage for migration planning.

## Installation

```bash
uv sync
```

Requires Python >= 3.14.

## Usage

### Fetch recent releases

List stable `n8n-nodes-base` releases from the npm registry:

```bash
uv run n8n-release-parser fetch-releases --months 6
```

### Diff two releases

Compare node catalogs between two versions (catalogs must already be stored):

```bash
uv run n8n-release-parser diff 1.70.0 1.71.0 --store-dir .n8n-catalog
```

### Build an API spec index

Index a directory of OpenAPI 3.x / Swagger 2.0 spec files:

```bash
uv run n8n-release-parser build-index specs/ --output spec_index.json
```

### Match nodes to API specs

Match catalog nodes against the spec index:

```bash
uv run n8n-release-parser match --version 1.71.0 --index-file spec_index.json
```

### Look up a node type

Query a node type across all stored catalogs:

```bash
uv run n8n-release-parser lookup n8n-nodes-base.slack --store-dir .n8n-catalog
```

### Generate a priority coverage report

Report on API mapping coverage for priority nodes:

```bash
uv run n8n-release-parser report --store-dir .n8n-catalog
```

All commands accept `--verbose` / `-v` for debug logging. Storage options (`--store-dir`, `--output`, `--index-file`) accept local paths or `s3://bucket/prefix` URIs.

## Architecture

```
src/n8n_release_parser/
  models.py        Pydantic data models (all frozen/immutable)
  fetcher.py       Async npm registry client (httpx)
  parser.py        Node description extraction from n8n packages
  differ.py        Catalog diffing with field-level change detection
  catalog.py       Persistence layer (NodeCatalogStore)
  storage.py       StorageBackend protocol + local filesystem impl
  storage_s3.py    S3 storage backend (boto3, lazy-imported)
  spec_index.py    OpenAPI/Swagger spec indexing
  matcher.py       Fuzzy node-to-spec matching (rapidfuzz)
  priority.py      Node classification & priority coverage reporting
  cli.py           Typer CLI wiring
```

### Key design decisions

- **Immutable models** — All Pydantic models use `frozen=True` for value-object semantics.
- **Pluggable storage** — A `StorageBackend` protocol abstracts local/S3 I/O. The factory `create_backend()` auto-detects `s3://` URIs.
- **Lazy imports** — `boto3` is only imported when an S3 URI is used, keeping the default dependency footprint light.
- **Layered matching** — `matcher.py` tries URL-based matching first, falls back to service-name matching, then verifies via operation-level fuzzy matching.
- **Cumulative catalogs** — `build_lookup()` merges catalogs oldest-to-newest so newer releases override while preserving historical versions.

### Node classification categories

Nodes are classified into translation strategies by `priority.py`:

| Classification | Meaning |
|---|---|
| `AWS_NATIVE` | Direct AWS SDK mapping (S3, DynamoDB, SQS, etc.) |
| `FLOW_CONTROL` | Core workflow nodes (if, switch, merge, set, etc.) |
| `TRIGGER` | Event trigger nodes |
| `PICOFUN_API` | Has a matched API spec |
| `GRAPHQL_API` | Targets a GraphQL endpoint |
| `CODE_JS` / `CODE_PYTHON` | Code/function nodes by language |
| `UNSUPPORTED` | No known translation strategy |

## Development

Run tests:

```bash
uv run pytest
```

Run tests excluding integration tests:

```bash
uv run pytest -m "not integration"
```

Run linting and formatting:

```bash
uv run ruff check --fix .
uv run ruff format .
```

Run type checking:

```bash
uv run ty check
```

Run test coverage:

```bash
uv run coverage run -m pytest
uv run coverage report -m
```
