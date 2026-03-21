"""
Shared fixtures for integration tests against a real AWS account.

Provides helpers to run the full Phaeton pipeline (analyze, translate,
package) and to deploy / tear-down the resulting CDK application via
CloudFormation.

**Prerequisites**

* Valid AWS credentials (environment variables or profile).
* ``npm`` available on ``$PATH`` (CDK CLI is invoked via ``npx``).
* Sufficient IAM permissions: CloudFormation, Lambda, Step Functions,
  DynamoDB, IAM, S3, SQS, KMS, Logs, CloudWatch.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import boto3
import pytest
from n8n_to_sfn.engine import TranslationEngine
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.code_node import CodeNodeTranslator
from n8n_to_sfn.translators.flow_control import FlowControlTranslator
from n8n_to_sfn.translators.triggers import TriggerTranslator
from phaeton_models.adapters.analyzer_to_translator import (
    convert_report_to_analysis,
)
from phaeton_models.adapters.translator_to_packager import (
    convert_output_to_packager_input,
)
from phaeton_models.translator_output import (
    TranslationOutput as BoundaryTranslationOutput,
)
from types_boto3_stepfunctions.client import SFNClient
from workflow_analyzer.analyzer import WorkflowAnalyzer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_CDK_DEPLOY_TIMEOUT = 600  # seconds
_CDK_DESTROY_TIMEOUT = 600
_SFN_EXECUTION_TIMEOUT = 300
_PHAETON_TEST_TAG = "phaeton-test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique_stack_name(base: str) -> str:
    """Return a unique CloudFormation stack name with a short random suffix."""
    suffix = uuid.uuid4().hex[:8]
    return f"{base}-{suffix}"


def _run_pipeline(workflow_path: Path, output_dir: Path) -> Path:
    """
    Run the full Phaeton pipeline and return the packager output directory.

    Stages:
        1. Analyse the n8n workflow JSON.
        2. Convert the analysis report to a ``WorkflowAnalysis``.
        3. Translate to ASL via the ``TranslationEngine``.
        4. Bridge the engine output to the boundary ``TranslationOutput``.
        5. Convert to ``PackagerInput``.
        6. Run the Packager to emit a deployable CDK app.
    """
    from n8n_to_sfn_packager.models.inputs import (
        PackagerInput as PkgPackagerInput,
    )
    from n8n_to_sfn_packager.packager import Packager

    workflow_data = json.loads(workflow_path.read_text())

    # Stage 1 - analyse
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze_dict(workflow_data)

    # Stage 2 - adapt (analyzer to translator)
    analysis = convert_report_to_analysis(report)

    # Stage 3 - translate
    engine = TranslationEngine(
        translators=[
            FlowControlTranslator(),
            AWSServiceTranslator(),
            TriggerTranslator(),
            CodeNodeTranslator(),
        ],
    )
    engine_output = engine.translate(analysis)

    # Stage 4 - bridge to boundary model
    engine_dict = engine_output.model_dump(mode="json")
    boundary_output = BoundaryTranslationOutput.model_validate(engine_dict)

    # Stage 5 - adapt (translator to packager)
    boundary_pkginput = convert_output_to_packager_input(
        boundary_output,
        workflow_name=workflow_data.get("name", "integration-test"),
    )

    # Stage 6 - bridge to packager's own model and package
    pkginput = PkgPackagerInput.model_validate(
        boundary_pkginput.model_dump(mode="json"),
    )
    packager = Packager()
    return packager.package(pkginput, output_dir)


def _cdk_deploy(
    cdk_dir: Path,
    stack_name: str,
    *,
    extra_context: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Deploy a CDK application and return the stack outputs.

    Tags every resource with ``phaeton-test`` for easy identification
    and manual cleanup.

    Returns
    -------
    dict[str, str]
        CloudFormation outputs keyed by OutputKey.

    """
    cmd = [
        "npx",
        "cdk",
        "deploy",
        "--all",
        "--require-approval=never",
        f"--tags={_PHAETON_TEST_TAG}=true",
        "--outputs-file=cdk-outputs.json",
    ]
    if extra_context:
        for key, value in extra_context.items():
            cmd.append(f"--context={key}={value}")

    logger.info("CDK deploy: %s (cwd=%s)", " ".join(cmd), cdk_dir)
    subprocess.run(  # noqa: S603
        cmd,
        cwd=cdk_dir,
        check=True,
        timeout=_CDK_DEPLOY_TIMEOUT,
        capture_output=True,
        text=True,
    )

    outputs_file = cdk_dir / "cdk-outputs.json"
    if outputs_file.exists():
        all_outputs = json.loads(outputs_file.read_text())
        merged: dict[str, str] = {}
        for _stack, outs in all_outputs.items():
            merged.update(outs)
        return merged
    return {}


def _cdk_destroy(cdk_dir: Path) -> None:
    """Tear down the CDK stacks deployed from *cdk_dir*."""
    cmd = ["npx", "cdk", "destroy", "--all", "--force"]
    logger.info("CDK destroy: %s (cwd=%s)", " ".join(cmd), cdk_dir)
    try:
        subprocess.run(  # noqa: S603
            cmd,
            cwd=cdk_dir,
            check=True,
            timeout=_CDK_DESTROY_TIMEOUT,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError, subprocess.TimeoutExpired:
        logger.exception("CDK destroy failed - manual cleanup may be required")


def _wait_for_execution(
    sfn_client: SFNClient,
    execution_arn: str,
    *,
    timeout: int = _SFN_EXECUTION_TIMEOUT,
    poll_interval: int = 5,
) -> dict[str, object]:
    """
    Poll a Step Functions execution until it reaches a terminal state.

    Returns
    -------
    dict
        The ``describe_execution`` response for the terminal state.

    Raises
    ------
    TimeoutError
        If the execution does not finish within *timeout* seconds.

    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = sfn_client.describe_execution(executionArn=execution_arn)
        status = resp["status"]
        if status in {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}:
            return resp
        time.sleep(poll_interval)
    msg = f"Execution {execution_arn} did not finish within {timeout}s"
    raise TimeoutError(msg)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def aws_region() -> str:
    """Return the AWS region to use for integration tests."""
    return os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(scope="session")
def sfn_client(aws_region: str) -> SFNClient:
    """Return a boto3 Step Functions client."""
    return boto3.client("stepfunctions", region_name=aws_region)


@pytest.fixture(scope="session")
def cfn_client(aws_region: str) -> object:
    """Return a boto3 CloudFormation client."""
    return boto3.client("cloudformation", region_name=aws_region)


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the integration test fixtures directory."""
    return _FIXTURES_DIR


@pytest.fixture
def pipeline_output(
    tmp_path: Path,
) -> Path:
    """
    Run the full pipeline for the simple DynamoDB workflow.

    Returns the packager output directory.
    """
    workflow_path = _FIXTURES_DIR / "simple_dynamodb_workflow.json"
    output_dir = tmp_path / "pipeline-output"
    return _run_pipeline(workflow_path, output_dir)


@pytest.fixture
def deployed_stack(
    pipeline_output: Path,
) -> Generator[dict[str, str]]:
    """
    Deploy the packaged CDK application and yield its stack outputs.

    Automatically destroys the stack after the test completes.
    """
    cdk_dir = pipeline_output / "cdk"

    # Install CDK dependencies
    subprocess.run(
        ["uv", "sync"],  # noqa: S607
        cwd=cdk_dir,
        check=True,
        timeout=120,
        capture_output=True,
        text=True,
    )

    stack_name = _unique_stack_name("phaeton-inttest")
    try:
        outputs = _cdk_deploy(
            cdk_dir,
            stack_name,
            extra_context={"stack_prefix": stack_name},
        )
        yield outputs
    finally:
        _cdk_destroy(cdk_dir)


# ---------------------------------------------------------------------------
# Pipeline-only fixture (no AWS deployment)
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline_result(tmp_path: Path) -> Path:
    """Run the pipeline and return the output directory without deploying."""
    workflow_path = _FIXTURES_DIR / "simple_dynamodb_workflow.json"
    output_dir = tmp_path / "pipeline-output"
    return _run_pipeline(workflow_path, output_dir)
