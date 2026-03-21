"""
Performance tests for the packaging pipeline stage.

Benchmarks the Packager (CDK code generation and file writing) with
synthetic workflows of increasing size to detect scaling regressions.

Run with::

    uv run pytest -m performance
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from n8n_to_sfn_packager.models.inputs import PackagerInput as PkgPackagerInput
from phaeton_models.adapters.analyzer_to_translator import (
    convert_report_to_analysis,
)
from phaeton_models.adapters.translator_to_packager import (
    convert_output_to_packager_input,
)
from phaeton_models.translator_output import (
    TranslationOutput as BoundaryTranslationOutput,
)

from tests.performance.conftest import (
    WORKFLOW_SIZES,
    BenchmarkResult,
    generate_workflow,
    make_analyzer,
    make_packager,
    make_translation_engine,
    run_timed,
)

# Maximum acceptable seconds for packaging a 200-node workflow.
_STAGE_TIMEOUT_SECONDS = 60.0

# Maximum acceptable scaling ratio (200-node / 100-node).
_MAX_SCALING_RATIO = 3.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _translate_workflow(workflow_data: dict[str, Any]) -> BoundaryTranslationOutput:
    """Run analyze + adapt + translate and return the boundary output."""
    analyzer = make_analyzer()
    report = analyzer.analyze_dict(workflow_data)
    analysis = convert_report_to_analysis(report)

    engine = make_translation_engine()
    engine_output = engine.translate(analysis)

    return BoundaryTranslationOutput.model_validate(
        engine_output.model_dump(mode="json"),
    )


def _run_packaging(
    workflow_data: dict[str, Any],
    output_dir: Path,
) -> BenchmarkResult:
    """Benchmark the packager stage on *workflow_data*."""
    boundary_output = _translate_workflow(workflow_data)
    workflow_name = workflow_data.get("name", "perf-test")
    boundary_pkginput = convert_output_to_packager_input(
        boundary_output,
        workflow_name=workflow_name,
    )
    pkginput = PkgPackagerInput.model_validate(
        boundary_pkginput.model_dump(mode="json"),
    )
    packager = make_packager()
    return run_timed(packager.package, pkginput, output_dir)


def _get_output_size(output_dir: Path) -> int:
    """Return the total size of all files under *output_dir* in bytes."""
    return sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.performance
class TestPackagingScaling:
    """Benchmark the Packager across workflow sizes."""

    @pytest.mark.parametrize("num_nodes", WORKFLOW_SIZES)
    def test_packaging_completes(
        self,
        num_nodes: int,
        tmp_path: Path,
    ) -> None:
        """Packager must finish without errors for each workflow size."""
        workflow = generate_workflow(num_nodes)
        out_dir = tmp_path / f"pkg-{num_nodes}"
        bench = _run_packaging(workflow, out_dir)

        result_dir = bench.result
        assert result_dir is not None
        assert Path(result_dir).exists()

        output_size = _get_output_size(Path(result_dir))
        print(
            f"\n[packaging] nodes={num_nodes}  "
            f"time={bench.elapsed_seconds:.3f}s  "
            f"peak_mem={bench.peak_memory_bytes / 1024:.1f}KB  "
            f"output_size={output_size / 1024:.1f}KB",
        )

    def test_packaging_within_time_limit(self, tmp_path: Path) -> None:
        """Packager must finish a 200-node workflow within the time limit."""
        workflow = generate_workflow(200)
        bench = _run_packaging(workflow, tmp_path / "pkg-200-time")
        assert bench.elapsed_seconds < _STAGE_TIMEOUT_SECONDS, (
            f"Packaging took {bench.elapsed_seconds:.1f}s on 200 nodes "
            f"(limit: {_STAGE_TIMEOUT_SECONDS}s)"
        )

    def test_packaging_scaling_ratio(self, tmp_path: Path) -> None:
        """Packaging time ratio (200 / 100 nodes) must stay below threshold."""
        bench_100 = _run_packaging(
            generate_workflow(100),
            tmp_path / "pkg-100",
        )
        bench_200 = _run_packaging(
            generate_workflow(200),
            tmp_path / "pkg-200",
        )

        ratio = bench_200.elapsed_seconds / max(bench_100.elapsed_seconds, 1e-9)
        print(
            f"\n[packaging scaling] 100-node={bench_100.elapsed_seconds:.3f}s  "
            f"200-node={bench_200.elapsed_seconds:.3f}s  ratio={ratio:.2f}",
        )
        assert ratio < _MAX_SCALING_RATIO, (
            f"Packaging scaling ratio {ratio:.2f} exceeds {_MAX_SCALING_RATIO} "
            f"— possible O(n²) regression"
        )

    def test_packaging_memory_growth_linear(self, tmp_path: Path) -> None:
        """Packager peak memory should grow roughly linearly with node count."""
        bench_100 = _run_packaging(
            generate_workflow(100),
            tmp_path / "pkg-mem-100",
        )
        bench_200 = _run_packaging(
            generate_workflow(200),
            tmp_path / "pkg-mem-200",
        )

        mem_ratio = bench_200.peak_memory_bytes / max(
            bench_100.peak_memory_bytes,
            1,
        )
        print(
            f"\n[packaging memory] 100-node={bench_100.peak_memory_bytes / 1024:.1f}KB  "
            f"200-node={bench_200.peak_memory_bytes / 1024:.1f}KB  ratio={mem_ratio:.2f}",
        )
        assert mem_ratio < _MAX_SCALING_RATIO, (
            f"Packaging memory ratio {mem_ratio:.2f} exceeds {_MAX_SCALING_RATIO}"
        )

    def test_output_size_scales_linearly(self, tmp_path: Path) -> None:
        """Generated output file size should scale roughly linearly."""
        bench_100 = _run_packaging(
            generate_workflow(100),
            tmp_path / "pkg-size-100",
        )
        bench_200 = _run_packaging(
            generate_workflow(200),
            tmp_path / "pkg-size-200",
        )

        size_100 = _get_output_size(Path(bench_100.result))
        size_200 = _get_output_size(Path(bench_200.result))
        size_ratio = size_200 / max(size_100, 1)

        print(
            f"\n[packaging output] 100-node={size_100 / 1024:.1f}KB  "
            f"200-node={size_200 / 1024:.1f}KB  ratio={size_ratio:.2f}",
        )
        assert size_ratio < _MAX_SCALING_RATIO, (
            f"Output size ratio {size_ratio:.2f} exceeds {_MAX_SCALING_RATIO}"
        )


@pytest.mark.performance
class TestFullPipelineScaling:
    """Benchmark the complete pipeline (analyze -> translate -> package)."""

    @pytest.mark.parametrize("num_nodes", WORKFLOW_SIZES)
    def test_full_pipeline_completes(
        self,
        num_nodes: int,
        tmp_path: Path,
    ) -> None:
        """Full pipeline must complete without errors for each size."""
        workflow = generate_workflow(num_nodes)

        def _full_pipeline() -> Path:
            analyzer = make_analyzer()
            report = analyzer.analyze_dict(workflow)
            analysis = convert_report_to_analysis(report)

            engine = make_translation_engine()
            engine_output = engine.translate(analysis)

            boundary_output = BoundaryTranslationOutput.model_validate(
                engine_output.model_dump(mode="json"),
            )
            boundary_pkginput = convert_output_to_packager_input(
                boundary_output,
                workflow_name=workflow.get("name", "perf-test"),
            )
            pkginput = PkgPackagerInput.model_validate(
                boundary_pkginput.model_dump(mode="json"),
            )
            packager = make_packager()
            return packager.package(pkginput, tmp_path / f"full-{num_nodes}")

        bench = run_timed(_full_pipeline)
        assert Path(bench.result).exists()

        print(
            f"\n[full pipeline] nodes={num_nodes}  "
            f"time={bench.elapsed_seconds:.3f}s  "
            f"peak_mem={bench.peak_memory_bytes / 1024:.1f}KB",
        )

    def test_full_pipeline_scaling_ratio(self, tmp_path: Path) -> None:
        """Full pipeline time ratio (200 / 100) must stay below threshold."""

        def _pipeline(num_nodes: int) -> BenchmarkResult:
            workflow = generate_workflow(num_nodes)

            def _run() -> Path:
                analyzer = make_analyzer()
                report = analyzer.analyze_dict(workflow)
                analysis = convert_report_to_analysis(report)

                engine = make_translation_engine()
                engine_output = engine.translate(analysis)

                boundary_output = BoundaryTranslationOutput.model_validate(
                    engine_output.model_dump(mode="json"),
                )
                boundary_pkginput = convert_output_to_packager_input(
                    boundary_output,
                    workflow_name=workflow.get("name", "perf-test"),
                )
                pkginput = PkgPackagerInput.model_validate(
                    boundary_pkginput.model_dump(mode="json"),
                )
                packager = make_packager()
                return packager.package(
                    pkginput,
                    tmp_path / f"ratio-{num_nodes}",
                )

            return run_timed(_run)

        bench_100 = _pipeline(100)
        bench_200 = _pipeline(200)

        ratio = bench_200.elapsed_seconds / max(bench_100.elapsed_seconds, 1e-9)
        print(
            f"\n[full pipeline scaling] "
            f"100-node={bench_100.elapsed_seconds:.3f}s  "
            f"200-node={bench_200.elapsed_seconds:.3f}s  ratio={ratio:.2f}",
        )
        assert ratio < _MAX_SCALING_RATIO, (
            f"Full pipeline scaling ratio {ratio:.2f} exceeds {_MAX_SCALING_RATIO} "
            f"— possible O(n²) regression"
        )
