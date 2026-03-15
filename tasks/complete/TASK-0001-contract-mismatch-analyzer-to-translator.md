# Contract Mismatch Analyzer To Translator

**Priority:** P0
**Effort:** M
**Gap Analysis Ref:** Item #1

## Overview

Component 2 (Workflow Analyzer) outputs a `ConversionReport` model. Component 3 (Translation Engine / n8n-to-sfn) expects a `WorkflowAnalysis` model. These are structurally incompatible with no adapter between them, meaning data cannot flow from the analyzer to the translator. This is a deployment blocker because the pipeline is broken at its first inter-component boundary.

Key mismatches:

- **Top-level models:** `ConversionReport` vs `WorkflowAnalysis` have different field names and types for classified nodes, dependency graphs, variables, expressions, payload warnings, and unsupported nodes.
- **ClassifiedNode:** Component 2 uses `category: NodeCategory` while Component 3 uses `classification: NodeClassification`. Component 2 has `translation_strategy` and `notes`; Component 3 has `expressions`, `api_spec`, and `operation_mappings`.
- **ClassifiedExpression:** Field name mismatches (`raw_expression` vs `original`, `referenced_nodes` vs `node_references`) and enum value mismatches (`VARIABLE_REFERENCE` vs `REQUIRES_VARIABLES`, `LAMBDA_REQUIRED` vs `REQUIRES_LAMBDA`).
- **Expressions location:** Component 2 stores expressions in a top-level `classified_expressions` list; Component 3 embeds them per-node in `ClassifiedNode.expressions`.
- **Dependency graph:** Component 2 uses an opaque `graph_metadata: dict[str, Any]`; Component 3 uses structured `dependency_edges: list[DependencyEdge]`.
- **Payload warnings:** Component 2 uses `list[PayloadWarning]` (structured objects); Component 3 uses `list[str]`.
- **Unsupported nodes:** Component 2 uses `list[ClassifiedNode]` (full objects); Component 3 uses `list[str]` (node names only).

## Dependencies

- **Blocked by:** TASK-0003 (shared `phaeton-models` package must exist first)
- **Blocks:** TASK-0007, TASK-0031, TASK-0032

## Acceptance Criteria

1. An adapter module exists that converts a `ConversionReport` instance into a valid `WorkflowAnalysis` instance.
2. All `NodeCategory` enum values map correctly to `NodeClassification` enum values.
3. All `ExpressionCategory` values map correctly: `VARIABLE_REFERENCE` -> `REQUIRES_VARIABLES`, `LAMBDA_REQUIRED` -> `REQUIRES_LAMBDA`, `JSONATA_DIRECT` -> `JSONATA_DIRECT`.
4. Top-level `classified_expressions` from Component 2 are redistributed to per-node `ClassifiedNode.expressions` lists in Component 3's format.
5. `graph_metadata: dict` is parsed into `dependency_edges: list[DependencyEdge]` with correct `from_node`, `to_node`, `edge_type`, and `output_index` fields.
6. `payload_warnings: list[PayloadWarning]` are converted to `list[str]`.
7. `unsupported_nodes: list[ClassifiedNode]` are converted to `list[str]` (node names).
8. Round-trip test: a `ConversionReport` with representative data converts to a `WorkflowAnalysis` and passes Pydantic validation.
9. `uv run pytest` passes with tests covering every field mapping.
10. `uv run ruff check` passes with no violations.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/adapters/__init__.py` (new)
- `shared/phaeton-models/src/phaeton_models/adapters/analyzer_to_translator.py` (new)
- `shared/phaeton-models/tests/test_adapter_analyzer_to_translator.py` (new)

### Technical Approach

1. Create an adapter function `convert_report_to_analysis(report: ConversionReport) -> WorkflowAnalysis`:
   - Map `report.classified_nodes` (each with `.category: NodeCategory`) to Component 3 `ClassifiedNode` (with `.classification: NodeClassification`).
   - Build a mapping from `NodeCategory` to `NodeClassification` — values are identical strings (`AWS_NATIVE`, `FLOW_CONTROL`, etc.) so conversion is by value.
   - Map `ExpressionCategory` values: `VARIABLE_REFERENCE` -> `REQUIRES_VARIABLES`, `LAMBDA_REQUIRED` -> `REQUIRES_LAMBDA`, `JSONATA_DIRECT` -> `JSONATA_DIRECT`.
   - For each classified expression in `report.classified_expressions`, assign it to the corresponding `ClassifiedNode.expressions` list by matching on `expression.node_name == node.node.name`.
   - Map expression fields: `raw_expression` -> `original`, `referenced_nodes` -> `node_references`.
   - Parse `report.graph_metadata` into `DependencyEdge` objects. Expected keys in `graph_metadata`: edges as dicts with `from_node`, `to_node`, `edge_type` (default `"CONNECTION"`), and optional `output_index`.
   - Convert `report.payload_warnings` to `list[str]` using `str(warning)` or `warning.message`.
   - Convert `report.unsupported_nodes` to `list[str]` using `[cn.node.name for cn in report.unsupported_nodes]`.
   - Carry over `report.confidence_score`.
   - Extract `variables_needed` from `report` context (if available) or default to empty dict.

2. The adapter should live in `phaeton-models` (the shared package from TASK-0003) since it sits at the boundary between components. It imports `ConversionReport` and related models from `workflow-analyzer`, and `WorkflowAnalysis` and related models from `n8n-to-sfn`. Both are already dependencies of `phaeton-models`' consumers, so the adapter avoids introducing new cross-component dependencies.

### Testing Requirements

- `shared/phaeton-models/tests/test_adapter_analyzer_to_translator.py`
- Test every field mapping with a fully populated `ConversionReport` fixture.
- Test edge cases: empty expressions list, no unsupported nodes, empty graph metadata.
- Verify Pydantic validation succeeds on the output `WorkflowAnalysis`.
- Verify expression redistribution: expressions for node "A" appear in `ClassifiedNode` for "A", not in node "B".
