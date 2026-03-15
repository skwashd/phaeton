"""Pydantic models for ASL state machine output.

These models produce JSON that validates against the ASL JSON schema
(``schemas/asl_schema.json``). All models use PascalCase aliases for JSON
serialization and default to JSONata query language.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

# ---------------------------------------------------------------------------
# Shared components
# ---------------------------------------------------------------------------


class RetryConfig(BaseModel):
    """A single retry rule for a Task, Map, or Parallel state.

    Example::

        RetryConfig(
            error_equals=["States.TaskFailed"],
            interval_seconds=2,
            max_attempts=3,
            backoff_rate=2.0,
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    error_equals: list[str] = Field(alias="ErrorEquals")
    interval_seconds: int | None = Field(default=None, alias="IntervalSeconds")
    max_attempts: int | None = Field(default=None, alias="MaxAttempts")
    backoff_rate: float | None = Field(default=None, alias="BackoffRate")
    max_delay_seconds: int | None = Field(default=None, alias="MaxDelaySeconds")
    jitter_strategy: Literal["FULL", "NONE"] | None = Field(
        default=None, alias="JitterStrategy"
    )

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {"ErrorEquals": self.error_equals}
        if self.interval_seconds is not None:
            result["IntervalSeconds"] = self.interval_seconds
        if self.max_attempts is not None:
            result["MaxAttempts"] = self.max_attempts
        if self.backoff_rate is not None:
            result["BackoffRate"] = self.backoff_rate
        if self.max_delay_seconds is not None:
            result["MaxDelaySeconds"] = self.max_delay_seconds
        if self.jitter_strategy is not None:
            result["JitterStrategy"] = self.jitter_strategy
        return result


class CatchConfig(BaseModel):
    """A single catch rule for a Task, Map, or Parallel state.

    Example::

        CatchConfig(
            error_equals=["States.ALL"],
            next="HandleError",
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    error_equals: list[str] = Field(alias="ErrorEquals")
    next: str = Field(alias="Next")
    result_path: str | None = Field(default=None, alias="ResultPath")
    comment: str | None = Field(default=None, alias="Comment")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ErrorEquals": self.error_equals,
            "Next": self.next,
        }
        if self.result_path is not None:
            result["ResultPath"] = self.result_path
        if self.comment is not None:
            result["Comment"] = self.comment
        return result


# ---------------------------------------------------------------------------
# Choice state operator
# ---------------------------------------------------------------------------


class ChoiceRule(BaseModel):
    """A single rule within a Choice state's ``Choices`` array.

    Supports JSONata ``Condition`` mode as well as JSONPath comparison operators.

    Example::

        ChoiceRule(condition="$states.input.age > 18", next="Adult")
    """

    model_config = ConfigDict(populate_by_name=True)

    # JSONata mode
    condition: str | None = Field(default=None, alias="Condition")

    # Routing
    next: str | None = Field(default=None, alias="Next")

    # Logical operators
    and_: list[ChoiceRule] | None = Field(default=None, alias="And")
    or_: list[ChoiceRule] | None = Field(default=None, alias="Or")
    not_: ChoiceRule | None = Field(default=None, alias="Not")

    # JSONPath variable
    variable: str | None = Field(default=None, alias="Variable")

    # Comparison operators (subset for common use)
    boolean_equals: bool | None = Field(default=None, alias="BooleanEquals")
    string_equals: str | None = Field(default=None, alias="StringEquals")
    numeric_equals: float | None = Field(default=None, alias="NumericEquals")
    numeric_greater_than: float | None = Field(default=None, alias="NumericGreaterThan")
    numeric_less_than: float | None = Field(default=None, alias="NumericLessThan")
    is_present: bool | None = Field(default=None, alias="IsPresent")
    is_null: bool | None = Field(default=None, alias="IsNull")
    string_matches: str | None = Field(default=None, alias="StringMatches")

    # Variable assignment
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")
    comment: str | None = Field(default=None, alias="Comment")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        field_map = {
            "condition": "Condition",
            "next": "Next",
            "variable": "Variable",
            "boolean_equals": "BooleanEquals",
            "string_equals": "StringEquals",
            "numeric_equals": "NumericEquals",
            "numeric_greater_than": "NumericGreaterThan",
            "numeric_less_than": "NumericLessThan",
            "is_present": "IsPresent",
            "is_null": "IsNull",
            "string_matches": "StringMatches",
            "assign": "Assign",
            "comment": "Comment",
        }
        for py_name, json_name in field_map.items():
            value = getattr(self, py_name)
            if value is not None:
                result[json_name] = value
        if self.and_ is not None:
            result["And"] = [r.model_dump(by_alias=True) for r in self.and_]
        if self.or_ is not None:
            result["Or"] = [r.model_dump(by_alias=True) for r in self.or_]
        if self.not_ is not None:
            result["Not"] = self.not_.model_dump(by_alias=True)
        return result


# ---------------------------------------------------------------------------
# Processor config for Map states
# ---------------------------------------------------------------------------


class ProcessorConfig(BaseModel):
    """Configuration for a Map state's ``ItemProcessor``.

    Example::

        ProcessorConfig(mode="INLINE")
    """

    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["INLINE", "DISTRIBUTED"] = Field(alias="Mode")
    execution_type: Literal["STANDARD", "EXPRESS"] | None = Field(
        default=None, alias="ExecutionType"
    )

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {"Mode": self.mode}
        if self.execution_type is not None:
            result["ExecutionType"] = self.execution_type
        return result


class ItemProcessor(BaseModel):
    """The ``ItemProcessor`` block inside a Map state.

    Example::

        ItemProcessor(
            processor_config=ProcessorConfig(mode="INLINE"),
            start_at="ProcessItem",
            states={"ProcessItem": PassState(type="Pass", end=True)},
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    processor_config: ProcessorConfig | None = Field(
        default=None, alias="ProcessorConfig"
    )
    start_at: str | None = Field(default=None, alias="StartAt")
    states: dict[str, Any] | None = Field(default=None, alias="States")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.processor_config is not None:
            result["ProcessorConfig"] = self.processor_config.model_dump(by_alias=True)
        if self.start_at is not None:
            result["StartAt"] = self.start_at
        if self.states is not None:
            states_out: dict[str, Any] = {}
            for name, state in self.states.items():
                if isinstance(state, BaseModel):
                    states_out[name] = state.model_dump(by_alias=True)
                else:
                    states_out[name] = state
            result["States"] = states_out
        return result


# ---------------------------------------------------------------------------
# State types
# ---------------------------------------------------------------------------


def _base_state_dict(
    state_type: str,
    *,
    comment: str | None = None,
    input_path: str | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Build the common fields shared by all states."""
    result: dict[str, Any] = {"Type": state_type}
    if comment is not None:
        result["Comment"] = comment
    if input_path is not None:
        result["InputPath"] = input_path
    if output_path is not None:
        result["OutputPath"] = output_path
    return result


def _add_next_or_end(
    result: dict[str, Any], next_: str | None, end: bool | None
) -> None:
    """Add ``Next`` or ``End`` to a state dict."""
    if next_ is not None:
        result["Next"] = next_
    elif end:
        result["End"] = True


class TaskState(BaseModel):
    """An ASL Task state that invokes an AWS resource.

    Example::

        TaskState(
            type="Task",
            resource="arn:aws:states:::aws-sdk:s3:getObject",
            arguments={"Bucket": "my-bucket", "Key": "file.json"},
            end=True,
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Task"] = Field(default="Task", alias="Type")
    resource: str = Field(alias="Resource")
    next: str | None = Field(default=None, alias="Next")
    end: bool | None = Field(default=None, alias="End")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    result_path: str | None = Field(default=None, alias="ResultPath")
    parameters: dict[str, Any] | None = Field(default=None, alias="Parameters")
    arguments: dict[str, Any] | None = Field(default=None, alias="Arguments")
    output: str | None = Field(default=None, alias="Output")
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")
    retry: list[RetryConfig] | None = Field(default=None, alias="Retry")
    catch: list[CatchConfig] | None = Field(default=None, alias="Catch")
    timeout_seconds: int | None = Field(default=None, alias="TimeoutSeconds")
    heartbeat_seconds: int | None = Field(default=None, alias="HeartbeatSeconds")
    credentials: dict[str, Any] | None = Field(default=None, alias="Credentials")
    result_selector: dict[str, Any] | None = Field(default=None, alias="ResultSelector")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Task",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        result["Resource"] = self.resource
        _add_next_or_end(result, self.next, self.end)
        for py, js in [
            ("result_path", "ResultPath"),
            ("parameters", "Parameters"),
            ("arguments", "Arguments"),
            ("output", "Output"),
            ("assign", "Assign"),
            ("timeout_seconds", "TimeoutSeconds"),
            ("heartbeat_seconds", "HeartbeatSeconds"),
            ("credentials", "Credentials"),
            ("result_selector", "ResultSelector"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        if self.retry is not None:
            result["Retry"] = [r.model_dump(by_alias=True) for r in self.retry]
        if self.catch is not None:
            result["Catch"] = [c.model_dump(by_alias=True) for c in self.catch]
        return result


class PassState(BaseModel):
    """An ASL Pass state that passes input to output with optional transformation.

    Example::

        PassState(type="Pass", end=True, output='{% $states.input %}')
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Pass"] = Field(default="Pass", alias="Type")
    next: str | None = Field(default=None, alias="Next")
    end: bool | None = Field(default=None, alias="End")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    result_path: str | None = Field(default=None, alias="ResultPath")
    result: Any | None = Field(default=None, alias="Result")
    parameters: dict[str, Any] | None = Field(default=None, alias="Parameters")
    output: str | None = Field(default=None, alias="Output")
    arguments: dict[str, Any] | None = Field(default=None, alias="Arguments")
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Pass",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        _add_next_or_end(result, self.next, self.end)
        for py, js in [
            ("result_path", "ResultPath"),
            ("result", "Result"),
            ("parameters", "Parameters"),
            ("output", "Output"),
            ("arguments", "Arguments"),
            ("assign", "Assign"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        return result


class ChoiceState(BaseModel):
    """An ASL Choice state that branches based on conditions.

    Example::

        ChoiceState(
            type="Choice",
            choices=[ChoiceRule(condition="$states.input.x > 0", next="Positive")],
            default="Negative",
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Choice"] = Field(default="Choice", alias="Type")
    choices: list[ChoiceRule] = Field(alias="Choices")
    default: str | None = Field(default=None, alias="Default")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    output: str | None = Field(default=None, alias="Output")
    arguments: dict[str, Any] | None = Field(default=None, alias="Arguments")
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Choice",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        result["Choices"] = [c.model_dump(by_alias=True) for c in self.choices]
        for py, js in [
            ("default", "Default"),
            ("output", "Output"),
            ("arguments", "Arguments"),
            ("assign", "Assign"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        return result


class WaitState(BaseModel):
    """An ASL Wait state that pauses execution.

    Example::

        WaitState(type="Wait", seconds=10, next="Continue")
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Wait"] = Field(default="Wait", alias="Type")
    next: str | None = Field(default=None, alias="Next")
    end: bool | None = Field(default=None, alias="End")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    seconds: int | None = Field(default=None, alias="Seconds")
    timestamp: str | None = Field(default=None, alias="Timestamp")
    seconds_path: str | None = Field(default=None, alias="SecondsPath")
    timestamp_path: str | None = Field(default=None, alias="TimestampPath")
    output: str | None = Field(default=None, alias="Output")
    arguments: dict[str, Any] | None = Field(default=None, alias="Arguments")
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Wait",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        _add_next_or_end(result, self.next, self.end)
        for py, js in [
            ("seconds", "Seconds"),
            ("timestamp", "Timestamp"),
            ("seconds_path", "SecondsPath"),
            ("timestamp_path", "TimestampPath"),
            ("output", "Output"),
            ("arguments", "Arguments"),
            ("assign", "Assign"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        return result


class SucceedState(BaseModel):
    """An ASL Succeed state (terminal).

    Example::

        SucceedState(type="Succeed")
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Succeed"] = Field(default="Succeed", alias="Type")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    output: str | None = Field(default=None, alias="Output")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Succeed",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        if self.output is not None:
            result["Output"] = self.output
        return result


class FailState(BaseModel):
    """An ASL Fail state (terminal).

    Example::

        FailState(type="Fail", error="CustomError", cause="Something went wrong")
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Fail"] = Field(default="Fail", alias="Type")
    comment: str | None = Field(default=None, alias="Comment")
    error: str | None = Field(default=None, alias="Error")
    error_path: str | None = Field(default=None, alias="ErrorPath")
    cause: str | None = Field(default=None, alias="Cause")
    cause_path: str | None = Field(default=None, alias="CausePath")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {"Type": "Fail"}
        for py, js in [
            ("comment", "Comment"),
            ("error", "Error"),
            ("error_path", "ErrorPath"),
            ("cause", "Cause"),
            ("cause_path", "CausePath"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        return result


class ParallelState(BaseModel):
    """An ASL Parallel state that executes branches concurrently.

    Example::

        ParallelState(
            type="Parallel",
            branches=[StateMachine(start_at="A", states={"A": PassState(end=True)})],
            end=True,
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Parallel"] = Field(default="Parallel", alias="Type")
    branches: list[StateMachine] = Field(alias="Branches")
    next: str | None = Field(default=None, alias="Next")
    end: bool | None = Field(default=None, alias="End")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    result_path: str | None = Field(default=None, alias="ResultPath")
    output: str | None = Field(default=None, alias="Output")
    arguments: dict[str, Any] | None = Field(default=None, alias="Arguments")
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")
    retry: list[RetryConfig] | None = Field(default=None, alias="Retry")
    catch: list[CatchConfig] | None = Field(default=None, alias="Catch")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Parallel",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        result["Branches"] = [b.model_dump(by_alias=True) for b in self.branches]
        _add_next_or_end(result, self.next, self.end)
        for py, js in [
            ("result_path", "ResultPath"),
            ("output", "Output"),
            ("arguments", "Arguments"),
            ("assign", "Assign"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        if self.retry is not None:
            result["Retry"] = [r.model_dump(by_alias=True) for r in self.retry]
        if self.catch is not None:
            result["Catch"] = [c.model_dump(by_alias=True) for c in self.catch]
        return result


class MapState(BaseModel):
    """An ASL Map state that iterates over a collection.

    Example::

        MapState(
            type="Map",
            item_processor=ItemProcessor(
                processor_config=ProcessorConfig(mode="INLINE"),
                start_at="Process",
                states={"Process": PassState(end=True)},
            ),
            end=True,
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["Map"] = Field(default="Map", alias="Type")
    next: str | None = Field(default=None, alias="Next")
    end: bool | None = Field(default=None, alias="End")
    comment: str | None = Field(default=None, alias="Comment")
    input_path: str | None = Field(default=None, alias="InputPath")
    output_path: str | None = Field(default=None, alias="OutputPath")
    result_path: str | None = Field(default=None, alias="ResultPath")
    items_path: str | None = Field(default=None, alias="ItemsPath")
    item_selector: dict[str, Any] | None = Field(default=None, alias="ItemSelector")
    item_processor: ItemProcessor | None = Field(default=None, alias="ItemProcessor")
    max_concurrency: int | None = Field(default=None, alias="MaxConcurrency")
    parameters: dict[str, Any] | None = Field(default=None, alias="Parameters")
    output: str | None = Field(default=None, alias="Output")
    arguments: dict[str, Any] | None = Field(default=None, alias="Arguments")
    assign: dict[str, Any] | None = Field(default=None, alias="Assign")
    retry: list[RetryConfig] | None = Field(default=None, alias="Retry")
    catch: list[CatchConfig] | None = Field(default=None, alias="Catch")
    label: str | None = Field(default=None, alias="Label")
    tolerated_failure_percentage: float | None = Field(
        default=None, alias="ToleratedFailurePercentage"
    )
    tolerated_failure_count: int | None = Field(
        default=None, alias="ToleratedFailureCount"
    )

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result = _base_state_dict(
            "Map",
            comment=self.comment,
            input_path=self.input_path,
            output_path=self.output_path,
        )
        _add_next_or_end(result, self.next, self.end)
        for py, js in [
            ("result_path", "ResultPath"),
            ("items_path", "ItemsPath"),
            ("item_selector", "ItemSelector"),
            ("max_concurrency", "MaxConcurrency"),
            ("parameters", "Parameters"),
            ("output", "Output"),
            ("arguments", "Arguments"),
            ("assign", "Assign"),
            ("label", "Label"),
            ("tolerated_failure_percentage", "ToleratedFailurePercentage"),
            ("tolerated_failure_count", "ToleratedFailureCount"),
        ]:
            val = getattr(self, py)
            if val is not None:
                result[js] = val
        if self.item_processor is not None:
            result["ItemProcessor"] = self.item_processor.model_dump(by_alias=True)
        if self.retry is not None:
            result["Retry"] = [r.model_dump(by_alias=True) for r in self.retry]
        if self.catch is not None:
            result["Catch"] = [c.model_dump(by_alias=True) for c in self.catch]
        return result


# ---------------------------------------------------------------------------
# Union type for any state
# ---------------------------------------------------------------------------

State = Annotated[
    TaskState
    | PassState
    | ChoiceState
    | WaitState
    | SucceedState
    | FailState
    | ParallelState
    | MapState,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Top-level state machine
# ---------------------------------------------------------------------------


class StateMachine(BaseModel):
    """An ASL state machine definition.

    Example::

        StateMachine(
            start_at="Start",
            states={"Start": PassState(end=True)},
        )
    """

    model_config = ConfigDict(populate_by_name=True)

    comment: str | None = Field(default=None, alias="Comment")
    start_at: str = Field(alias="StartAt")
    states: dict[
        str,
        TaskState
        | PassState
        | ChoiceState
        | WaitState
        | SucceedState
        | FailState
        | ParallelState
        | MapState,
    ] = Field(alias="States")
    query_language: Literal["JSONata"] | None = Field(
        default="JSONata", alias="QueryLanguage"
    )
    version: str | None = Field(default=None, alias="Version")
    timeout_seconds: int | None = Field(default=None, alias="TimeoutSeconds")

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.query_language is not None:
            result["QueryLanguage"] = self.query_language
        if self.comment is not None:
            result["Comment"] = self.comment
        result["StartAt"] = self.start_at
        states_out: dict[str, Any] = {}
        for name, state in self.states.items():
            if isinstance(state, BaseModel):
                states_out[name] = state.model_dump(by_alias=True)
            else:
                states_out[name] = state
        result["States"] = states_out
        if self.version is not None:
            result["Version"] = self.version
        if self.timeout_seconds is not None:
            result["TimeoutSeconds"] = self.timeout_seconds
        return result
