"""Shared Lambda bundling helpers for CDK stacks."""

from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_ssm as ssm
from constructs import Construct

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)

_EXCLUDE = [
    ".git",
    ".venv",
    "node_modules",
    "cdk.out",
    ".ruff_cache",
    "*.pyc",
    "*/cli.py",
    "*/__main__.py",
]


def bundled_code(component_dir: str) -> lambda_.Code:
    """
    Create a Lambda Code asset with all dependencies bundled via Docker.

    Parameters
    ----------
    component_dir:
        Relative path from the repository root to the component directory
        (e.g. ``"workflow-analyzer"``).

    """
    return lambda_.Code.from_asset(
        _REPO_ROOT,
        bundling=cdk.BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_13.bundling_image,
            command=[
                "bash",
                "-c",
                "pip wheel /asset-input/shared/phaeton-models"
                " -w /tmp/wheels --no-deps -q && "
                f"pip install /asset-input/{component_dir}"
                " --find-links /tmp/wheels -t /asset-output -q && "
                "find /asset-output -type d -name __pycache__"
                " -exec rm -rf {} + 2>/dev/null; "
                "find /asset-output -name '*.dist-info' -type d"
                " -exec rm -rf {} + 2>/dev/null; true",
            ],
        ),
        exclude=_EXCLUDE,
    )


def bundled_adapter_code() -> lambda_.Code:
    """
    Create a Lambda Code asset for the adapter handler.

    Installs ``phaeton-models`` and copies the adapter handler script.
    ``aws-lambda-powertools`` is provided by the Powertools Layer at runtime.
    """
    return lambda_.Code.from_asset(
        _REPO_ROOT,
        bundling=cdk.BundlingOptions(
            image=lambda_.Runtime.PYTHON_3_13.bundling_image,
            command=[
                "bash",
                "-c",
                "pip wheel /asset-input/shared/phaeton-models"
                " -w /tmp/wheels --no-deps -q && "
                "pip install phaeton-models"
                " --find-links /tmp/wheels -t /asset-output -q && "
                "cp /asset-input/deployment/functions/adapter/handler.py"
                " /asset-output/ && "
                "find /asset-output -type d -name __pycache__"
                " -exec rm -rf {} + 2>/dev/null; "
                "find /asset-output -name '*.dist-info' -type d"
                " -exec rm -rf {} + 2>/dev/null; true",
            ],
        ),
        exclude=[
            ".git",
            ".venv",
            "node_modules",
            "cdk.out",
            ".ruff_cache",
            "*.pyc",
        ],
    )


def powertools_layer(scope: Construct) -> lambda_.ILayerVersion:
    """Look up the AWS-managed Lambda Powertools Layer for Python (ARM64)."""
    return lambda_.LayerVersion.from_layer_version_arn(
        scope,
        "PowertoolsLayer",
        ssm.StringParameter.value_for_string_parameter(
            scope,
            "/aws/service/powertools/python/v3/arm64/latest",
        ),
    )
