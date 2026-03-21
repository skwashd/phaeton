"""
Performance tests for the analysis and translation pipeline stages.

Benchmarks the Workflow Analyzer and Translation Engine with synthetic
workflows of increasing size to detect scaling regressions.

Run with::

    uv run pytest -m performance
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
from phaeton_models.adapters.analyzer_to_translator import (
    convert_report_to_analysis,
)

from tests.performance.conftest import (
    WORKFLOW_SIZES,
    BenchmarkResult,
    generate_workflow,
    make_analyzer,
    make_translation_engine,
    run_timed,
)

# Maximum acceptable seconds for any single stage on a 200-node workflow.
_STAGE_TIMEOUT_SECONDS = 60.0

# Maximum acceptable ratio between the 200-node and 100-node times.
# A ratio of 4.0 would indicate O(n²); we allow up to 3.5 to account
# for constant-factor noise while still catching quadratic regressions.
_MAX_SCALING_RATIO = 3.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_analysis(workflow_data: dict[str, Any]) -> BenchmarkResult:
    """Benchmark the analyzer stage on *workflow_data*."""
    analyzer = make_analyzer()
    return run_timed(analyzer.analyze_dict, workflow_data)


def _run_translation(workflow_data: dict[str, Any]) -> BenchmarkResult:
    """Benchmark analyze + adapt + translate on *workflow_data*."""
    analyzer = make_analyzer()
    report = analyzer.analyze_dict(workflow_data)
    analysis = convert_report_to_analysis(report)

    engine = make_translation_engine()
    return run_timed(engine.translate, analysis)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.performance
class TestAnalyzerScaling:
    """Benchmark the Workflow Analyzer across workflow sizes."""

    @pytest.mark.parametrize("num_nodes", WORKFLOW_SIZES)
    def test_analyzer_completes(self, num_nodes: int) -> None:
        """Analyzer must finish without errors for each workflow size."""
        workflow = generate_workflow(num_nodes)
        bench = _run_analysis(workflow)

        report = bench.result
        assert report is not None
        assert report.total_nodes == num_nodes

        # Print benchmark data for visibility.
        print(
            f"\n[analyzer] nodes={num_nodes}  "
            f"time={bench.elapsed_seconds:.3f}s  "
            f"peak_mem={bench.peak_memory_bytes / 1024:.1f}KB",
        )

    def test_analyzer_within_time_limit(self) -> None:
        """Analyzer must finish a 200-node workflow within the time limit."""
        workflow = generate_workflow(200)
        bench = _run_analysis(workflow)
        assert bench.elapsed_seconds < _STAGE_TIMEOUT_SECONDS, (
            f"Analyzer took {bench.elapsed_seconds:.1f}s on 200 nodes "
            f"(limit: {_STAGE_TIMEOUT_SECONDS}s)"
        )

    def test_analyzer_scaling_ratio(self) -> None:
        """Analyzer time ratio (200 / 100 nodes) must stay below threshold."""
        bench_100 = _run_analysis(generate_workflow(100))
        bench_200 = _run_analysis(generate_workflow(200))

        ratio = bench_200.elapsed_seconds / max(bench_100.elapsed_seconds, 1e-9)
        print(
            f"\n[analyzer scaling] 100-node={bench_100.elapsed_seconds:.3f}s  "
            f"200-node={bench_200.elapsed_seconds:.3f}s  ratio={ratio:.2f}",
        )
        assert ratio < _MAX_SCALING_RATIO, (
            f"Analyzer scaling ratio {ratio:.2f} exceeds {_MAX_SCALING_RATIO} "
            f"— possible O(n²) regression"
        )

    def test_analyzer_memory_growth_linear(self) -> None:
        """Analyzer peak memory should grow roughly linearly with node count."""
        bench_100 = _run_analysis(generate_workflow(100))
        bench_200 = _run_analysis(generate_workflow(200))

        mem_ratio = bench_200.peak_memory_bytes / max(
            bench_100.peak_memory_bytes,
            1,
        )
        print(
            f"\n[analyzer memory] 100-node={bench_100.peak_memory_bytes / 1024:.1f}KB  "
            f"200-node={bench_200.peak_memory_bytes / 1024:.1f}KB  ratio={mem_ratio:.2f}",
        )
        # Allow up to 3.5x for a 2x increase in nodes (linear + overhead).
        assert mem_ratio < _MAX_SCALING_RATIO, (
            f"Analyzer memory ratio {mem_ratio:.2f} exceeds {_MAX_SCALING_RATIO}"
        )


@pytest.mark.performance
class TestTranslationEngineScaling:
    """Benchmark the Translation Engine across workflow sizes."""

    @pytest.mark.parametrize("num_nodes", WORKFLOW_SIZES)
    def test_translation_completes(self, num_nodes: int) -> None:
        """Translation must finish without errors for each workflow size."""
        workflow = generate_workflow(num_nodes)
        bench = _run_translation(workflow)

        output = bench.result
        assert output is not None
        assert output.state_machine is not None

        print(
            f"\n[translation] nodes={num_nodes}  "
            f"time={bench.elapsed_seconds:.3f}s  "
            f"peak_mem={bench.peak_memory_bytes / 1024:.1f}KB",
        )

    def test_translation_within_time_limit(self) -> None:
        """Translation must finish a 200-node workflow within the time limit."""
        workflow = generate_workflow(200)
        bench = _run_translation(workflow)
        assert bench.elapsed_seconds < _STAGE_TIMEOUT_SECONDS, (
            f"Translation took {bench.elapsed_seconds:.1f}s on 200 nodes "
            f"(limit: {_STAGE_TIMEOUT_SECONDS}s)"
        )

    def test_translation_scaling_ratio(self) -> None:
        """Translation time ratio (200 / 100 nodes) must stay below threshold."""
        bench_100 = _run_translation(generate_workflow(100))
        bench_200 = _run_translation(generate_workflow(200))

        ratio = bench_200.elapsed_seconds / max(bench_100.elapsed_seconds, 1e-9)
        print(
            f"\n[translation scaling] 100-node={bench_100.elapsed_seconds:.3f}s  "
            f"200-node={bench_200.elapsed_seconds:.3f}s  ratio={ratio:.2f}",
        )
        assert ratio < _MAX_SCALING_RATIO, (
            f"Translation scaling ratio {ratio:.2f} exceeds {_MAX_SCALING_RATIO} "
            f"— possible O(n²) regression"
        )

    def test_translation_memory_growth_linear(self) -> None:
        """Translation peak memory should grow roughly linearly with node count."""
        bench_100 = _run_translation(generate_workflow(100))
        bench_200 = _run_translation(generate_workflow(200))

        mem_ratio = bench_200.peak_memory_bytes / max(
            bench_100.peak_memory_bytes,
            1,
        )
        print(
            f"\n[translation memory] 100-node={bench_100.peak_memory_bytes / 1024:.1f}KB  "
            f"200-node={bench_200.peak_memory_bytes / 1024:.1f}KB  ratio={mem_ratio:.2f}",
        )
        assert mem_ratio < _MAX_SCALING_RATIO, (
            f"Translation memory ratio {mem_ratio:.2f} exceeds {_MAX_SCALING_RATIO}"
        )

    def test_translation_output_size_scales_linearly(self) -> None:
        """Serialized ASL output size should scale roughly linearly."""
        bench_100 = _run_translation(generate_workflow(100))
        bench_200 = _run_translation(generate_workflow(200))

        size_100 = sys.getsizeof(
            bench_100.result.state_machine.model_dump_json(),
        )
        size_200 = sys.getsizeof(
            bench_200.result.state_machine.model_dump_json(),
        )
        size_ratio = size_200 / max(size_100, 1)

        print(
            f"\n[translation output] 100-node={size_100}B  "
            f"200-node={size_200}B  ratio={size_ratio:.2f}",
        )
        assert size_ratio < _MAX_SCALING_RATIO, (
            f"Output size ratio {size_ratio:.2f} exceeds {_MAX_SCALING_RATIO}"
        )
