# Complex Expression Translation

**Priority:** P2
**Effort:** L
**Gap Analysis Ref:** Item #24

## Overview

Expressions classified as `LAMBDA_REQUIRED` / `REQUIRES_LAMBDA` (Category C) require a Lambda function to evaluate. This depends on the AI agent being functional (TASK-0008). Until the AI agent works, any workflow with complex expressions that reference multiple upstream nodes or use JavaScript built-ins cannot be translated. These expressions are too complex for direct JSONata translation and require runtime evaluation.

## Dependencies

- **Blocked by:** TASK-0008 (AI agent needed for generating Lambda evaluation code)
- **Blocks:** None

## Acceptance Criteria

1. Expressions classified as `REQUIRES_LAMBDA` (in `n8n-to-sfn`) or `LAMBDA_REQUIRED` (in `workflow-analyzer`) produce a Lambda function that evaluates the expression.
2. The Lambda function receives the expression's input data and returns the evaluated result.
3. The generated Lambda code correctly resolves references to multiple upstream nodes.
4. JavaScript built-in methods (e.g., `Math.round`, `Date.now`, `JSON.parse`) are handled in the Lambda runtime.
5. The AI agent (when available) is used to generate the Lambda evaluation code for expressions it understands.
6. A fallback exists for expressions the AI agent cannot translate (warning + placeholder).
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py` (new)
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (integrate expression evaluation)
- `n8n-to-sfn/tests/test_expression_evaluator.py` (new)

### Technical Approach

1. **Expression evaluation Lambda:**
   - For each `REQUIRES_LAMBDA` expression, generate a Lambda function that:
     - Receives the expression's input context (upstream node outputs).
     - Evaluates the expression using the appropriate runtime (Node.js for JavaScript expressions).
     - Returns the result.

2. **Expression patterns to handle:**
   - Multi-node references: `{{ $node["Node A"].data.field + $node["Node B"].data.field }}`
   - JavaScript built-ins: `{{ Math.round($json.value * 100) / 100 }}`
   - String operations: `{{ $json.name.toUpperCase() }}`
   - Date operations: `{{ DateTime.now().toISO() }}`
   - Conditional expressions: `{{ $json.status === "active" ? "yes" : "no" }}`

3. **AI agent integration:**
   - Pass the expression to the AI agent via `translate_expression(expr, node, context)`.
   - The AI agent returns the Lambda evaluation code.
   - Wrap the returned code in a Lambda handler template.

4. **State machine integration:**
   - Insert a `TaskState` invoking the expression Lambda before the state that uses the expression result.
   - Wire the Lambda output to the consuming state's input.

### Testing Requirements

- Test simple multi-reference expressions.
- Test JavaScript built-in method expressions.
- Test date/time expressions with `luxon`.
- Test conditional expressions.
- Test AI agent integration for expression translation.
