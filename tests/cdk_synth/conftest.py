"""
Shared fixtures for CDK synthesis validation tests.

Runs the Phaeton pipeline for representative workflows, then dynamically
imports the generated CDK stacks and synthesizes them into CloudFormation
templates for assertion.

These tests do NOT require AWS credentials -- ``cdk synth`` runs locally
via the Python CDK API with asset bundling disabled.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from tests.e2e.conftest import PipelineResult, run_pipeline

_FIXTURES_DIR = Path(__file__).parent.parent / "e2e" / "fixtures"

# Context key that tells CDK to skip Docker-based asset bundling.
# This allows Lambda bundling (Code.from_asset with BundlingOptions)
# to synthesize without requiring Docker in the test environment.
_NO_BUNDLING_CONTEXT = {"aws:cdk:bundling-stacks": []}


class SynthResult:
    """Holds the synthesized templates and pipeline result for a workflow."""

    def __init__(
        self,
        *,
        pipeline_result: PipelineResult,
        workflow_template: Template,
        shared_template: Template,
        workflow_cfn: Mapping[str, Any],
        shared_cfn: Mapping[str, Any],
    ) -> None:
        """Store synthesized templates and pipeline result."""
        self.pipeline_result = pipeline_result
        self.workflow_template = workflow_template
        self.shared_template = shared_template
        self.workflow_cfn = workflow_cfn
        self.shared_cfn = shared_cfn


def _synth_generated_stacks(output_dir: Path) -> tuple[Template, Template]:
    """
    Dynamically import generated CDK stacks and synthesize them.

    Args:
        output_dir: The pipeline output directory containing ``cdk/``.

    Returns:
        A ``(workflow_template, shared_template)`` tuple.

    """
    cdk_dir = output_dir / "cdk"

    # Purge previously-imported generated modules to avoid cross-test
    # contamination (each workflow generates its own stacks package).
    for mod_name in list(sys.modules):
        if mod_name == "stacks" or mod_name.startswith("stacks."):
            del sys.modules[mod_name]

    sys.path.insert(0, str(cdk_dir))
    try:
        # Force-import the generated stacks package from *this* cdk_dir.
        stacks_pkg = importlib.import_module("stacks")
        importlib.reload(stacks_pkg)

        shared_mod = importlib.import_module("stacks.shared_stack")
        importlib.reload(shared_mod)

        workflow_mod = importlib.import_module("stacks.workflow_stack")
        importlib.reload(workflow_mod)

        shared_stack_cls = shared_mod.SharedStack
        workflow_stack_cls = workflow_mod.WorkflowStack

        app = cdk.App(context=_NO_BUNDLING_CONTEXT)
        shared = shared_stack_cls(app, "TestShared")
        workflow = workflow_stack_cls(
            app, "TestWorkflow", shared_stack=shared
        )

        return Template.from_stack(workflow), Template.from_stack(shared)
    finally:
        sys.path.remove(str(cdk_dir))
        for mod_name in list(sys.modules):
            if mod_name == "stacks" or mod_name.startswith("stacks."):
                del sys.modules[mod_name]


def _build_synth_result(
    pipeline_result: PipelineResult,
) -> SynthResult:
    """Run CDK synth on a pipeline result and return a ``SynthResult``."""
    wf_template, shared_template = _synth_generated_stacks(
        pipeline_result.output_dir,
    )
    return SynthResult(
        pipeline_result=pipeline_result,
        workflow_template=wf_template,
        shared_template=shared_template,
        workflow_cfn=wf_template.to_json(),
        shared_cfn=shared_template.to_json(),
    )


@pytest.fixture
def simple_dynamodb_synth(tmp_path: Path) -> SynthResult:
    """Synthesize the simple DynamoDB workflow CDK application."""
    result = run_pipeline(
        _FIXTURES_DIR / "simple_dynamodb.json",
        tmp_path / "simple-dynamodb-output",
    )
    return _build_synth_result(result)


@pytest.fixture
def code_node_synth(tmp_path: Path) -> SynthResult:
    """Synthesize the Code node (Lambda) workflow CDK application."""
    result = run_pipeline(
        _FIXTURES_DIR / "code_node.json",
        tmp_path / "code-node-output",
    )
    return _build_synth_result(result)


@pytest.fixture
def scheduled_synth(tmp_path: Path) -> SynthResult:
    """Synthesize the scheduled trigger workflow CDK application."""
    result = run_pipeline(
        _FIXTURES_DIR / "scheduled.json",
        tmp_path / "scheduled-output",
    )
    return _build_synth_result(result)
