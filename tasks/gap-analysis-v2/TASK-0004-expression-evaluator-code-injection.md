# Expression Evaluator Code Injection

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #4

## Overview

`_build_expression_code()` at `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py:124-127` directly interpolates user-provided n8n expressions into generated JavaScript Lambda code:

```python
inner = _strip_expression_wrapper(expr)
return f"  const expressionResult = {inner};"
```

An n8n expression like `={{ 1; process.exit(0); // }}` would produce:

```javascript
const expressionResult = 1; process.exit(0); //;
```

This is valid JavaScript that executes arbitrary code in the generated Lambda function. The same pattern appears at line 250 in `_try_ai_agent()` for AI-translated expressions.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0010 (lint suppressions at lines 252 and 273 in the same file may change during this refactoring)

## Acceptance Criteria

1. User-provided expressions are validated/sanitized before interpolation into JavaScript code.
2. Expressions containing dangerous patterns (`process`, `require`, `eval`, `Function`, `import`, semicolons outside string literals) are rejected with a clear error.
3. The AI agent fallback path (line 250) applies the same validation.
4. A blocklist-based or AST-based approach prevents injection of arbitrary JavaScript statements.
5. Legitimate n8n expressions (property access, arithmetic, string operations, ternary operators) continue to work.
6. `uv run pytest` passes in `n8n-to-sfn/`.
7. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py`
- `n8n-to-sfn/tests/` — add injection tests

### Technical Approach

1. **Create a validation function** `_validate_expression(expr: str) -> None` that raises `ValueError` if the expression contains dangerous patterns:
   ```python
   _DANGEROUS_PATTERNS = [
       r'\bprocess\b',
       r'\brequire\b',
       r'\beval\b',
       r'\bFunction\b',
       r'\bimport\b',
       r'\bglobal\b',
       r'\bwindow\b',
       r';',  # statement separator
       r'\{',  # block statements (outside template literals)
   ]
   ```

2. **Call the validator** in `_build_expression_code()` at line 124 before interpolation:
   ```python
   _validate_expression(inner)
   return f"  const expressionResult = {inner};"
   ```

3. **Apply the same validation** in `_try_ai_agent()` at line 250 before using AI-translated expressions.

4. **Consider an allowlist approach** as a more robust alternative: only permit expressions matching a safe grammar (property access chains, arithmetic operators, string methods, ternary operators, template literals). This is more restrictive but eliminates the cat-and-mouse game of blocklist updates.

5. **Handle edge cases:** Some legitimate n8n expressions may contain curly braces (template literals) or other blocked characters. The validator should distinguish between template literal syntax `${...}` and block statements `{ ... }`.

### Testing Requirements

- `n8n-to-sfn/tests/test_expression_evaluator.py` — add tests for:
  - Known injection payloads are rejected: `{{ 1; process.exit(0); // }}`, `{{ eval("malicious") }}`, `{{ require("child_process").exec("rm -rf /") }}`
  - Legitimate expressions pass validation: `{{ $json.name }}`, `{{ $json.count + 1 }}`, `{{ $json.active ? "yes" : "no" }}`, `{{ $json.items.map(i => i.name) }}`
  - AI agent fallback path also rejects injection payloads
  - Error messages are clear about why an expression was rejected
