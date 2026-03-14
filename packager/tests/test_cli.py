"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from n8n_to_sfn_packager.__main__ import app
from n8n_to_sfn_packager.models.inputs import (
    ConversionReport,
    CredentialSpec,
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
    PackagerInput,
    StateMachineDefinition,
    TriggerSpec,
    TriggerType,
    WorkflowMetadata,
)

runner = CliRunner()


def _schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[1] / ".." / "docs" / "asl_schema.json"
    ).resolve()


def _make_input_json() -> str:
    inp = PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="cli-test",
            source_n8n_version="1.42.0",
            converter_version="0.1.0",
            timestamp="2025-06-15T10:30:00Z",
            confidence_score=0.95,
        ),
        state_machine=StateMachineDefinition(
            asl={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
        ),
        lambda_functions=[
            LambdaFunctionSpec(
                function_name="my_func",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): return event",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/cli-test/creds/token",
                credential_type="apiKey",
            ),
        ],
        triggers=[
            TriggerSpec(
                trigger_type=TriggerType.MANUAL,
                configuration={},
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=2,
            confidence_score=0.95,
        ),
    )
    return inp.model_dump_json(indent=2)


class TestCli:
    """Tests for the CLI entry point."""

    def test_successful_run(self, tmp_path: Path) -> None:
        """Test a successful CLI run produces expected output."""
        input_file = tmp_path / "input.json"
        input_file.write_text(_make_input_json())
        output_dir = tmp_path / "output"

        result = runner.invoke(
            app,
            [
                "-i",
                str(input_file),
                "-o",
                str(output_dir),
                "--schema",
                str(_schema_path()),
            ],
        )
        assert result.exit_code == 0
        assert "Packaging complete!" in result.output
        assert (output_dir / "statemachine" / "definition.asl.json").exists()

    def test_invalid_input_file(self, tmp_path: Path) -> None:
        """Test that an invalid input file causes a non-zero exit code."""
        input_file = tmp_path / "bad.json"
        input_file.write_text("{}")

        result = runner.invoke(
            app,
            ["-i", str(input_file), "-o", str(tmp_path / "output")],
        )
        assert result.exit_code != 0

    def test_invalid_asl(self, tmp_path: Path) -> None:
        """Test that invalid ASL causes exit code 1."""
        inp_json = json.loads(_make_input_json())
        inp_json["state_machine"]["asl"] = {"States": {"Foo": {"Type": "Succeed"}}}
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(inp_json))

        result = runner.invoke(
            app,
            [
                "-i",
                str(input_file),
                "-o",
                str(tmp_path / "output"),
                "--schema",
                str(_schema_path()),
            ],
        )
        assert result.exit_code == 1
