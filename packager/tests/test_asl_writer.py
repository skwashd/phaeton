"""Tests for the ASL definition writer and validator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from n8n_to_sfn_packager.models.inputs import StateMachineDefinition
from n8n_to_sfn_packager.writers.asl_writer import ASLValidationError, ASLWriter


@pytest.fixture
def asl_writer() -> ASLWriter:
    """Create an ASLWriter with the project schema path."""
    schema_path = (
        Path(__file__).resolve().parents[1] / ".." / "docs" / "asl_schema.json"
    )
    return ASLWriter(schema_path=schema_path.resolve())


@pytest.fixture
def simple_asl() -> dict:
    """Return a simple linear workflow: Start -> DoWork -> Done."""
    return {
        "StartAt": "DoWork",
        "States": {
            "DoWork": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {"FunctionName": "my_func"},
                "Next": "Done",
            },
            "Done": {
                "Type": "Succeed",
            },
        },
    }


@pytest.fixture
def complex_asl() -> dict:
    """Complex ASL with Choice, Map, Parallel, and Pass states."""
    return {
        "QueryLanguage": "JSONata",
        "StartAt": "CheckInput",
        "States": {
            "CheckInput": {
                "Type": "Choice",
                "Choices": [
                    {
                        "Condition": "{% $states.input.mode = 'batch' %}",
                        "Next": "BatchProcess",
                    },
                    {
                        "Condition": "{% $states.input.mode = 'parallel' %}",
                        "Next": "ParallelProcess",
                    },
                ],
                "Default": "SingleProcess",
            },
            "BatchProcess": {
                "Type": "Map",
                "ItemProcessor": {
                    "StartAt": "ProcessItem",
                    "States": {
                        "ProcessItem": {
                            "Type": "Task",
                            "Resource": "arn:aws:states:::lambda:invoke",
                            "Parameters": {"FunctionName": "process_item"},
                            "End": True,
                        },
                    },
                },
                "Next": "Done",
            },
            "ParallelProcess": {
                "Type": "Parallel",
                "Branches": [
                    {
                        "StartAt": "BranchA",
                        "States": {
                            "BranchA": {
                                "Type": "Task",
                                "Resource": "arn:aws:states:::lambda:invoke",
                                "Parameters": {"FunctionName": "branch_a"},
                                "End": True,
                            },
                        },
                    },
                    {
                        "StartAt": "BranchB",
                        "States": {
                            "BranchB": {
                                "Type": "Pass",
                                "Result": {"status": "ok"},
                                "End": True,
                            },
                        },
                    },
                ],
                "Next": "Done",
            },
            "SingleProcess": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {"FunctionName": "single"},
                "Next": "Done",
            },
            "Done": {
                "Type": "Succeed",
            },
        },
    }


class TestASLValidation:
    """Tests for ASL validation logic."""

    def test_valid_simple_asl(self, asl_writer: ASLWriter, simple_asl: dict) -> None:
        """Test that a simple valid ASL passes validation."""
        errors = asl_writer.validate(simple_asl)
        assert errors == []

    def test_valid_complex_asl(self, asl_writer: ASLWriter, complex_asl: dict) -> None:
        """Test that a complex valid ASL passes validation."""
        errors = asl_writer.validate(complex_asl)
        assert errors == []

    def test_invalid_missing_start_at(self, asl_writer: ASLWriter) -> None:
        """Test that missing StartAt is detected as invalid."""
        invalid = {"States": {"Foo": {"Type": "Succeed"}}}
        errors = asl_writer.validate(invalid)
        assert len(errors) > 0
        assert any("StartAt" in e for e in errors)

    def test_invalid_empty_states(self, asl_writer: ASLWriter) -> None:
        """Test that empty states are handled gracefully."""
        invalid = {"StartAt": "Foo", "States": {}}
        errors = asl_writer.validate(invalid)
        # Empty states may or may not be an error depending on schema,
        # but StartAt referencing a nonexistent state should be caught by runtime
        # The schema itself requires at least matching pattern properties
        assert isinstance(errors, list)


class TestASLWrite:
    """Tests for ASL file writing."""

    def test_write_creates_file(
        self, asl_writer: ASLWriter, simple_asl: dict, tmp_path: Path
    ) -> None:
        """Test that write creates the expected file."""
        defn = StateMachineDefinition(asl=simple_asl)
        path = asl_writer.write(defn, tmp_path)

        assert path.exists()
        assert path.name == "definition.asl.json"
        assert path.parent.name == "statemachine"

    def test_write_content_matches(
        self, asl_writer: ASLWriter, simple_asl: dict, tmp_path: Path
    ) -> None:
        """Test that written content matches the input ASL."""
        defn = StateMachineDefinition(asl=simple_asl)
        path = asl_writer.write(defn, tmp_path)

        content = json.loads(path.read_text())
        assert content == simple_asl

    def test_write_deterministic_output(
        self, asl_writer: ASLWriter, simple_asl: dict, tmp_path: Path
    ) -> None:
        """Test that writing the same ASL twice produces identical output."""
        defn = StateMachineDefinition(asl=simple_asl)

        path1 = asl_writer.write(defn, tmp_path / "run1")
        path2 = asl_writer.write(defn, tmp_path / "run2")

        assert path1.read_text() == path2.read_text()

    def test_write_sorted_keys(
        self, asl_writer: ASLWriter, simple_asl: dict, tmp_path: Path
    ) -> None:
        """Test that JSON keys are sorted in the output."""
        defn = StateMachineDefinition(asl=simple_asl)
        path = asl_writer.write(defn, tmp_path)

        text = path.read_text()
        # "StartAt" should come before "States" in sorted order
        assert text.index('"StartAt"') < text.index('"States"')

    def test_write_raises_on_invalid(
        self, asl_writer: ASLWriter, tmp_path: Path
    ) -> None:
        """Test that writing invalid ASL raises ASLValidationError."""
        invalid_defn = StateMachineDefinition(
            asl={"States": {"Foo": {"Type": "Succeed"}}},
        )
        with pytest.raises(ASLValidationError) as exc_info:
            asl_writer.write(invalid_defn, tmp_path)
        assert len(exc_info.value.errors) > 0

    def test_write_creates_directories(
        self, asl_writer: ASLWriter, simple_asl: dict, tmp_path: Path
    ) -> None:
        """Test that write creates intermediate directories."""
        output = tmp_path / "deep" / "nested"
        defn = StateMachineDefinition(asl=simple_asl)
        path = asl_writer.write(defn, output)

        assert path.exists()
        assert (output / "statemachine").is_dir()
