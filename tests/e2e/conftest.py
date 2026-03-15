"""Shared fixtures for end-to-end pipeline tests.

Provides helpers to run the full Phaeton pipeline (analyze -> adapt ->
translate -> adapt -> package) and return both the final output directory
and intermediate results for boundary validation.

These tests do NOT require AWS credentials -- they validate the pipeline
output locally without deploying.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from n8n_to_sfn.engine import TranslationEngine
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.code_node import CodeNodeTranslator
from n8n_to_sfn.translators.database import DatabaseTranslator
from n8n_to_sfn.translators.flow_control import FlowControlTranslator
from n8n_to_sfn.translators.http_request import HttpRequestTranslator
from n8n_to_sfn.translators.picofun import PicoFunTranslator
from n8n_to_sfn.translators.saas.airtable import AirtableTranslator
from n8n_to_sfn.translators.saas.gmail import GmailTranslator
from n8n_to_sfn.translators.saas.google_sheets import GoogleSheetsTranslator
from n8n_to_sfn.translators.saas.notion import NotionTranslator
from n8n_to_sfn.translators.saas.slack import SlackTranslator
from n8n_to_sfn.translators.set_node import SetNodeTranslator
from n8n_to_sfn.translators.triggers import TriggerTranslator
from phaeton_models.adapters.analyzer_to_translator import (
    convert_report_to_analysis,
)
from phaeton_models.adapters.translator_to_packager import (
    convert_output_to_packager_input,
)
from phaeton_models.analyzer import ConversionReport
from phaeton_models.translator import WorkflowAnalysis
from phaeton_models.translator_output import (
    TranslationOutput as BoundaryTranslationOutput,
)
from workflow_analyzer.analyzer import WorkflowAnalyzer

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass
class PipelineResult:
    """Captures all intermediate and final pipeline outputs."""

    workflow_data: dict[str, Any]
    report: ConversionReport
    analysis: WorkflowAnalysis
    boundary_output: BoundaryTranslationOutput
    output_dir: Path


def run_pipeline(workflow_path: Path, output_dir: Path) -> PipelineResult:
    """Run the full Phaeton pipeline, capturing intermediate results.

    Stages
    ------
    1. Analyse the n8n workflow JSON.
    2. Adapt analyzer report to translator input.
    3. Translate to ASL via the default engine.
    4. Bridge engine output to boundary TranslationOutput.
    5. Adapt to PackagerInput.
    6. Package into a deployable CDK application.
    """
    from n8n_to_sfn_packager.models.inputs import (
        PackagerInput as PkgPackagerInput,
    )
    from n8n_to_sfn_packager.packager import Packager

    workflow_data = json.loads(workflow_path.read_text())

    # Stage 1 -- analyse
    analyzer = WorkflowAnalyzer()
    report = analyzer.analyze_dict(workflow_data)

    # Stage 2 -- adapt (analyzer -> translator)
    analysis = convert_report_to_analysis(report)

    # Stage 3 -- translate
    engine = TranslationEngine(
        translators=[
            FlowControlTranslator(),
            AWSServiceTranslator(),
            TriggerTranslator(),
            CodeNodeTranslator(),
            DatabaseTranslator(),
            HttpRequestTranslator(),
            SetNodeTranslator(),
            SlackTranslator(),
            GmailTranslator(),
            GoogleSheetsTranslator(),
            NotionTranslator(),
            AirtableTranslator(),
            PicoFunTranslator(),
        ],
    )
    engine_output = engine.translate(analysis)

    # Stage 4 -- bridge to boundary model
    engine_dict = engine_output.model_dump(mode="json")
    boundary_output = BoundaryTranslationOutput.model_validate(engine_dict)

    # Stage 5 -- adapt (translator -> packager)
    boundary_pkginput = convert_output_to_packager_input(
        boundary_output,
        workflow_name=workflow_data.get("name", "e2e-test"),
    )

    # Stage 6 -- bridge to packager's own model and package
    pkginput = PkgPackagerInput.model_validate(
        boundary_pkginput.model_dump(mode="json"),
    )
    packager = Packager()
    result_dir = packager.package(pkginput, output_dir)

    return PipelineResult(
        workflow_data=workflow_data,
        report=report,
        analysis=analysis,
        boundary_output=boundary_output,
        output_dir=result_dir,
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the e2e test fixtures directory."""
    return _FIXTURES_DIR


@pytest.fixture
def simple_dynamodb_result(tmp_path: Path) -> PipelineResult:
    """Run pipeline for the simple DynamoDB workflow."""
    return run_pipeline(
        _FIXTURES_DIR / "simple_dynamodb.json",
        tmp_path / "simple-dynamodb-output",
    )


@pytest.fixture
def code_node_result(tmp_path: Path) -> PipelineResult:
    """Run pipeline for the Code node workflow."""
    return run_pipeline(
        _FIXTURES_DIR / "code_node.json",
        tmp_path / "code-node-output",
    )


@pytest.fixture
def scheduled_result(tmp_path: Path) -> PipelineResult:
    """Run pipeline for the scheduled trigger workflow."""
    return run_pipeline(
        _FIXTURES_DIR / "scheduled.json",
        tmp_path / "scheduled-output",
    )
