# ADR-003: JSONata as the Step Functions Query Language

**Status:** Accepted
**Date:** 2025-06-01

## Context

AWS Step Functions supports two query languages for data transformation within state machines: JSONPath (the legacy default) and JSONata (introduced in 2024 as a modern alternative). The translation engine must choose one language for all generated ASL, since mixing languages within a single state machine adds complexity and limits composability.

n8n workflows use a JavaScript-like expression syntax (`{{ $json.field }}`) for data references and transformations. These expressions include string methods, array operations (map, filter, reduce, sort), object merging, and conditional logic — all of which need equivalent representations in the target query language.

## Decision

All generated state machines use JSONata exclusively. The ASL `QueryLanguage` field is set to `"JSONata"` and all data transformations, Choice state conditions, and input/output processing use JSONata syntax (`{% expression %}`).

The expression translator maps n8n patterns to JSONata equivalents:
- Array spread (`[...$json.a, ...$json.b]`) → `$append()`
- Object merge (`{...$json.a, ...$json.b}`) → `$merge()`
- String methods (`toUpperCase()`, `trim()`, `split()`) → `$uppercase()`, `$trim()`, `$split()`
- Array operations (`map`, `filter`, `reduce`) → JSONata path expressions and aggregation functions (`$sum()`, `$sort()`)

## Consequences

### Positive
- JSONata is significantly more expressive than JSONPath, supporting functions, conditionals, string manipulation, and aggregations natively — reducing the number of n8n expressions that require Lambda fallbacks.
- JSONata syntax aligns more naturally with n8n's JavaScript-like expressions, making translations more direct and readable.
- AWS is actively investing in JSONata support, making it the forward-looking choice.

### Negative
- JSONata has a smaller community and less documentation compared to JSONPath, which may slow debugging for users unfamiliar with it.
- Some complex n8n expressions (multi-step variable resolution, node-specific globals like `$input.first()`) still require Lambda fallbacks even with JSONata's richer syntax.
- Existing Step Functions tutorials and examples predominantly use JSONPath, so generated ASL may look unfamiliar to users accustomed to the legacy syntax.

### Neutral
- The expression translator classifies n8n expressions into three categories: `JSONATA_DIRECT` (translatable), `REQUIRES_VARIABLES` (needs Step Functions variable resolution), and `REQUIRES_LAMBDA` (requires a custom Lambda function). This classification drives both the Workflow Analyzer's feasibility report and the Translation Engine's code generation.
