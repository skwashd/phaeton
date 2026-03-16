"""Tests for error handling translation (build_error_handling / apply_error_handling)."""

from __future__ import annotations

from phaeton_models.translator import ClassifiedNode, NodeClassification

from n8n_to_sfn.models.asl import RetryConfig, TaskState
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import apply_error_handling, build_error_handling


def _node_with_error_settings(
    *,
    continue_on_fail: bool | None = None,
    retry_on_fail: bool | None = None,
    max_tries: int | None = None,
    wait_between_tries: int | None = None,
) -> ClassifiedNode:
    """Create a classified node with error handling settings."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id="TestNode",
            name="TestNode",
            type="n8n-nodes-base.set",
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters={},
            continueOnFail=continue_on_fail,  # type: ignore[unknown-argument]
            retryOnFail=retry_on_fail,  # type: ignore[unknown-argument]
            maxTries=max_tries,  # type: ignore[unknown-argument]
            waitBetweenTries=wait_between_tries,  # type: ignore[unknown-argument]
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


class TestBuildErrorHandling:
    """Tests for build_error_handling."""

    def test_no_error_settings_no_retry_no_catch(self) -> None:
        """Test no error settings produces no retry or catch."""
        node = _node_with_error_settings()
        retries, catches = build_error_handling(node)
        assert retries == []
        assert catches == []

    def test_continue_on_fail_produces_catch(self) -> None:
        """Test continueOnFail produces catch configuration."""
        node = _node_with_error_settings(continue_on_fail=True)
        _retries, catches = build_error_handling(node, next_state_name="NextState")
        assert len(catches) == 1
        assert catches[0].error_equals == ["States.ALL"]
        assert catches[0].next == "NextState"

    def test_continue_on_fail_without_next_state_no_catch(self) -> None:
        """Test continueOnFail without next state produces no catch."""
        node = _node_with_error_settings(continue_on_fail=True)
        _retries, catches = build_error_handling(node, next_state_name=None)
        assert catches == []

    def test_retry_on_fail_produces_retry(self) -> None:
        """Test retryOnFail produces retry configuration."""
        node = _node_with_error_settings(
            retry_on_fail=True, max_tries=5, wait_between_tries=2000
        )
        retries, _catches = build_error_handling(node)
        assert len(retries) == 1
        assert retries[0].max_attempts == 5
        assert retries[0].interval_seconds == 2
        assert retries[0].error_equals == ["States.ALL"]

    def test_retry_on_fail_defaults(self) -> None:
        """Test retryOnFail uses defaults when not specified."""
        node = _node_with_error_settings(retry_on_fail=True)
        retries, _catches = build_error_handling(node)
        assert len(retries) == 1
        assert retries[0].max_attempts == 3
        assert retries[0].interval_seconds == 1

    def test_default_retry_used_when_no_explicit_retry(self) -> None:
        """Test default retry is used when no explicit retry."""
        node = _node_with_error_settings()
        default = RetryConfig(  # type: ignore[missing-argument]
            error_equals=["States.TaskFailed"],  # type: ignore[unknown-argument]
            max_attempts=2,
            interval_seconds=5,
        )
        retries, _catches = build_error_handling(node, default_retry=default)
        assert len(retries) == 1
        assert retries[0].error_equals == ["States.TaskFailed"]
        assert retries[0].max_attempts == 2

    def test_explicit_retry_overrides_default(self) -> None:
        """Test explicit retry overrides default retry."""
        node = _node_with_error_settings(retry_on_fail=True, max_tries=10)
        default = RetryConfig(  # type: ignore[missing-argument]
            error_equals=["States.TaskFailed"],  # type: ignore[unknown-argument]
            max_attempts=2,
            interval_seconds=5,
        )
        retries, _catches = build_error_handling(node, default_retry=default)
        assert len(retries) == 1
        assert retries[0].max_attempts == 10
        assert retries[0].error_equals == ["States.ALL"]

    def test_both_retry_and_catch(self) -> None:
        """Test both retry and catch are produced."""
        node = _node_with_error_settings(
            retry_on_fail=True,
            max_tries=3,
            continue_on_fail=True,
        )
        retries, catches = build_error_handling(node, next_state_name="Fallback")
        assert len(retries) == 1
        assert len(catches) == 1


class TestApplyErrorHandling:
    """Tests for apply_error_handling."""

    def test_applies_retry_to_task_state(self) -> None:
        """Test retry is applied to task state."""
        state = TaskState(resource="arn:aws:states:::lambda:invoke")  # type: ignore[missing-argument, unknown-argument]
        node = _node_with_error_settings(retry_on_fail=True, max_tries=4)
        result = apply_error_handling(state, node)
        assert result.retry is not None
        assert len(result.retry) == 1
        assert result.retry[0].max_attempts == 4

    def test_applies_catch_to_task_state(self) -> None:
        """Test catch is applied to task state."""
        state = TaskState(resource="arn:aws:states:::lambda:invoke")  # type: ignore[missing-argument, unknown-argument]
        node = _node_with_error_settings(continue_on_fail=True)
        result = apply_error_handling(state, node, next_state_name="HandleError")
        assert result.catch is not None
        assert len(result.catch) == 1
        assert result.catch[0].next == "HandleError"

    def test_no_modification_when_no_settings(self) -> None:
        """Test no modification when no error settings."""
        state = TaskState(resource="arn:aws:states:::lambda:invoke")  # type: ignore[missing-argument, unknown-argument]
        node = _node_with_error_settings()
        result = apply_error_handling(state, node)
        assert result.retry is None
        assert result.catch is None

    def test_default_retry_applied_to_state(self) -> None:
        """Test default retry is applied to state."""
        state = TaskState(resource="arn:aws:states:::lambda:invoke")  # type: ignore[missing-argument, unknown-argument]
        node = _node_with_error_settings()
        default = RetryConfig(  # type: ignore[missing-argument]
            error_equals=["States.TaskFailed"],  # type: ignore[unknown-argument]
            max_attempts=3,
            interval_seconds=2,
            backoff_rate=2.0,
            max_delay_seconds=30,
        )
        result = apply_error_handling(state, node, default_retry=default)
        assert result.retry is not None
        assert len(result.retry) == 1
        assert result.retry[0].backoff_rate == 2.0
        assert result.retry[0].max_delay_seconds == 30
