"""Tests for ASL validator."""

from __future__ import annotations

from n8n_to_sfn.models.asl import (
    FailState,
    PassState,
    StateMachine,
    TaskState,
)
from n8n_to_sfn.validator import validate_asl, validate_asl_json


class TestValidator:
    """Tests for ASL validator."""

    def test_valid_state_machine(self) -> None:
        """Test valid state machine has no errors."""
        sm = StateMachine(start_at="S", states={"S": PassState(end=True)})
        errors = validate_asl(sm)
        assert errors == []

    def test_missing_start_at(self) -> None:
        """Test missing StartAt produces error."""
        asl = {"States": {"S": {"Type": "Pass", "End": True}}}
        errors = validate_asl_json(asl)
        assert len(errors) > 0
        assert any("StartAt" in e for e in errors)

    def test_state_without_next_or_end(self) -> None:
        """Test state without Next or End produces error."""
        asl = {
            "StartAt": "S",
            "States": {
                "S": {"Type": "Pass"},
            },
        }
        errors = validate_asl_json(asl)
        assert len(errors) > 0

    def test_valid_complete_machine(self) -> None:
        """Test valid complete state machine has no errors."""
        sm = StateMachine(
            start_at="Start",
            states={
                "Start": PassState(next="End"),
                "End": PassState(end=True),
            },
        )
        errors = validate_asl(sm)
        assert errors == []

    def test_valid_task_state(self) -> None:
        """Test valid task state has no errors."""
        sm = StateMachine(
            start_at="T",
            states={
                "T": TaskState(
                    resource="arn:aws:states:::lambda:invoke",
                    end=True,
                ),
            },
        )
        errors = validate_asl(sm)
        assert errors == []

    def test_valid_fail_state(self) -> None:
        """Test valid fail state has no errors."""
        sm = StateMachine(
            start_at="F",
            states={"F": FailState(error="Err", cause="Bad")},
        )
        errors = validate_asl(sm)
        assert errors == []

    def test_errors_are_descriptive(self) -> None:
        """Test errors are descriptive strings."""
        asl = {"States": {}}
        errors = validate_asl_json(asl)
        assert len(errors) > 0
        for error in errors:
            assert isinstance(error, str)
            assert len(error) > 5

    def test_empty_states_missing_start(self) -> None:
        """Test empty states with missing start has no errors."""
        asl = {"StartAt": "X", "States": {}}
        errors = validate_asl_json(asl)
        assert errors == []
