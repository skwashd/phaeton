# Code Node N8n Runtime Globals

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #14

## Overview

The Code node translator passes n8n JavaScript code into a Lambda handler template without validating or rewriting n8n-specific globals. The handler exposes `event.items` but does not inject `$input`, `$json`, `$items`, `$node`, or other n8n built-ins. Code referencing these globals will fail at runtime with `ReferenceError`. The translator emits a warning asking users to "review handler for n8n-specific globals" but performs no detection or transformation.

Additionally, `luxon` is bundled as a dependency (hardcoded at line 52 in `_detect_js_dependencies`) but `DateTime` usage from `luxon` in user code is not validated against the Lambda Node.js runtime environment.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The Code node translator detects usage of n8n globals (`$input`, `$json`, `$items`, `$node`, `$env`, `$workflow`, `$execution`, `$prevNode`, `$parameter`) in user code.
2. For each detected global, the translator either:
   a. Injects a compatibility shim that maps the global to Lambda event data, or
   b. Rewrites references to use the Lambda handler's `event` parameter.
3. `$input.all()`, `$input.first()`, `$input.last()` are mapped to `event.items` array access.
4. `$json` is mapped to `event.items[0].json` (first item's JSON data).
5. `$items` is mapped to `event.items` (all items).
6. `$node` access patterns are mapped to execution context metadata.
7. A warning is emitted for globals that cannot be automatically translated (e.g., `$env`, `$execution`).
8. The `luxon` `DateTime` import is validated and included in the generated handler preamble.
9. `uv run pytest` passes in `n8n-to-sfn/`.
10. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/code_node.py`
- `n8n-to-sfn/tests/` (add/update Code node tests)

### Technical Approach

1. **Global detection** (add to `CodeNodeTranslator`):
   - Scan the user code string for n8n globals using regex patterns: `\$input`, `\$json`, `\$items`, `\$node`, `\$env`, etc.
   - Build a set of detected globals.

2. **Shim injection** (modify `_JS_TEMPLATE` at line 18):
   - Prepend compatibility shims to the handler before the user code:
     ```javascript
     const $input = {
       all: () => event.items,
       first: () => event.items[0],
       last: () => event.items[event.items.length - 1],
       item: event.items[0],
     };
     const $json = event.items[0]?.json ?? {};
     const $items = event.items;
     ```
   - Only inject shims for globals that are actually used in the code.

3. **Python equivalent** (modify `_PY_TEMPLATE` at line 30):
   - Add similar shims for Python code nodes that reference `$input`, etc.

4. **Warning for untranslatable globals:**
   - `$env` (n8n environment variables) -> emit warning, suggest using Lambda environment variables.
   - `$execution` (execution metadata) -> emit warning, suggest using Lambda context.
   - `$workflow` (workflow metadata) -> emit warning, suggest using Lambda environment variable.

5. **luxon validation** (line 52):
   - If `DateTime` is detected in user code, ensure `const { DateTime } = require('luxon');` is in the handler preamble.
   - The dependency `luxon` is already added by `_detect_js_dependencies`.

### Testing Requirements

- Test code with `$input.all()` usage is correctly shimmed.
- Test code with `$json` references maps to `event.items[0].json`.
- Test code with no n8n globals produces no shims.
- Test code with untranslatable globals emits appropriate warnings.
- Test `luxon` `DateTime` usage is handled.
