# Release Parser Caching

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #19

## Overview

The parser is entirely stateless. Every invocation of `extract_descriptions_from_package()` re-reads all `.node.json` files from disk and re-parses every node description via `parse_node_description()`. For the full n8n package (~400 node types), this is redundant work on every run. A SHA-256 hash comparison against previously parsed output would allow skipping unchanged nodes, saving compute time during incremental updates.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The parser caches parsed node descriptions with a content hash (SHA-256) of the source `.node.json` file.
2. On subsequent runs, unchanged files are skipped and their cached `NodeTypeEntry` results are reused.
3. Changed or new files are parsed and the cache is updated.
4. Deleted files have their entries removed from the cache.
5. The cache is stored in a configurable location (default: `~/.cache/phaeton/release-parser/`).
6. A `--no-cache` option bypasses the cache for full re-parsing.
7. Cache invalidation works correctly when the parser version changes.
8. `uv run pytest` passes in `n8n-release-parser/`.
9. `uv run ruff check` passes in `n8n-release-parser/`.

## Implementation Details

### Files to Modify

- `n8n-release-parser/src/n8n_release_parser/parser.py`
- `n8n-release-parser/src/n8n_release_parser/cache.py` (new)
- `n8n-release-parser/tests/test_cache.py` (new)

### Technical Approach

1. **Cache module** (`cache.py`):
   - `NodeCache` class with a JSON-based cache file.
   - Cache key: file path (relative to package directory).
   - Cache value: `{"sha256": "<hash>", "entries": [<serialized NodeTypeEntry>...], "parser_version": "<version>"}`.
   - Methods: `get(file_path, content_hash) -> list[NodeTypeEntry] | None`, `put(file_path, content_hash, entries)`, `remove(file_path)`, `save()`, `load()`.

2. **Integration with `extract_descriptions_from_package`** (line 203):
   - Before calling `parse_node_description` for each file, compute SHA-256 of the file content.
   - Check the cache: if hash matches, use cached entries.
   - If hash differs or no cache entry, parse the file and update the cache.
   - After processing all files, remove cache entries for files that no longer exist.

3. **Cache location:**
   - Default: `~/.cache/phaeton/release-parser/cache.json`.
   - Configurable via `cache_dir` parameter on `extract_descriptions_from_package`.

4. **Version-based invalidation:**
   - Store the parser version in the cache metadata.
   - If the parser version changes, invalidate the entire cache.

### Testing Requirements

- `n8n-release-parser/tests/test_cache.py`
- Test cache hit: same file content returns cached entries without re-parsing.
- Test cache miss: changed file content triggers re-parsing.
- Test new file: added file is parsed and cached.
- Test deleted file: removed file's cache entry is cleaned up.
- Test `--no-cache` flag bypasses the cache.
- Test cache corruption recovery (invalid JSON, missing fields).
