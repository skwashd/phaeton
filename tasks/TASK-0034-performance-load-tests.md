# Performance Load Tests

**Priority:** Testing
**Effort:** M
**Gap Analysis Ref:** Testing table row 4

## Overview

No performance or load tests exist for large workflows (100+ nodes). The translation engine and packager may have O(n^2) or worse scaling behavior for large graphs. Without performance testing, there is no baseline for translation time, memory usage, or output quality degradation on complex workflows.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A performance test suite exists that benchmarks the pipeline with workflows of varying sizes (10, 50, 100, 200 nodes).
2. Tests measure and report: translation time, peak memory usage, output file size.
3. Performance baselines are established and documented.
4. Tests detect O(n^2) or worse scaling regressions by comparing times across sizes.
5. Tests verify that the pipeline completes without errors for 200+ node workflows.
6. No individual pipeline stage takes longer than 60 seconds for a 200-node workflow.
7. `uv run pytest -m performance` runs the performance tests.

## Implementation Details

### Files to Modify

- `tests/performance/` (new directory at repo root)
- `tests/performance/conftest.py` (workflow generators, benchmarking fixtures)
- `tests/performance/test_translation_scaling.py`
- `tests/performance/test_packaging_scaling.py`

### Technical Approach

1. **Synthetic workflow generator:**
   ```python
   def generate_workflow(num_nodes: int) -> dict:
       """Generate a synthetic n8n workflow with the specified number of nodes."""
       nodes = [make_trigger_node()]
       for i in range(num_nodes - 1):
           node_type = random.choice(["dynamodb", "lambda", "sns", "sqs"])
           nodes.append(make_node(f"Node_{i}", node_type))
       connections = make_linear_connections(nodes)
       return {"nodes": nodes, "connections": connections}
   ```

2. **Benchmarking with pytest-benchmark or manual timing:**
   ```python
   @pytest.mark.performance
   @pytest.mark.parametrize("num_nodes", [10, 50, 100, 200])
   def test_translation_scaling(num_nodes, benchmark):
       workflow = generate_workflow(num_nodes)
       result = benchmark(lambda: translate_workflow(workflow))
       assert result is not None
   ```

3. **Memory profiling:**
   - Use `tracemalloc` to measure peak memory usage.
   - Assert memory growth is linear (not quadratic) with node count.

4. **Scaling regression detection:**
   - Compare time ratios: `time(200_nodes) / time(100_nodes)` should be < 4x for O(n^2) and < 2.5x for ~O(n).
   - Flag if the ratio exceeds the threshold.

5. **Components to benchmark:**
   - Workflow Analyzer: node classification speed.
   - Translation Engine: `translate()` method, especially `_topological_sort` and `_wire_transitions`.
   - Packager: CDK code generation and file writing.

### Testing Requirements

- Performance tests should be marked with `@pytest.mark.performance` to run separately.
- Tests should be deterministic (seed random generators).
- Tests should output benchmark results to stdout or a report file.
- Tests should not depend on external services.
