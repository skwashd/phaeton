"""Tests for the translator-to-packager adapter."""

import pytest

from phaeton_models.adapters.translator_to_packager import (
    convert_output_to_packager_input,
    map_runtime,
    map_trigger_type,
)
from phaeton_models.packager_input import (
    LambdaFunctionType,
    PackagerInput,
)
from phaeton_models.packager_input import (
    LambdaRuntime as PkgLambdaRuntime,
)
from phaeton_models.packager_input import (
    TriggerType as PkgTriggerType,
)
from phaeton_models.translator_output import (
    CredentialArtifact,
    LambdaArtifact,
    TranslationOutput,
    TriggerArtifact,
)
from phaeton_models.translator_output import (
    LambdaRuntime as EngLambdaRuntime,
)
from phaeton_models.translator_output import (
    TriggerType as EngTriggerType,
)

# ---------------------------------------------------------------------------
# Enum mapping tests
# ---------------------------------------------------------------------------


class TestRuntimeMapping:
    """Each LambdaRuntime value maps correctly."""

    def test_python_maps_to_lowercase(self) -> None:
        """PYTHON maps to python."""
        assert map_runtime(EngLambdaRuntime.PYTHON) == PkgLambdaRuntime.PYTHON
        assert str(PkgLambdaRuntime.PYTHON) == "python"

    def test_nodejs_maps_to_lowercase(self) -> None:
        """NODEJS maps to nodejs."""
        assert map_runtime(EngLambdaRuntime.NODEJS) == PkgLambdaRuntime.NODEJS
        assert str(PkgLambdaRuntime.NODEJS) == "nodejs"

    def test_unknown_runtime_raises(self) -> None:
        """Unrecognised runtime raises ValueError."""
        with pytest.raises(ValueError, match="Unknown LambdaRuntime"):
            map_runtime("RUBY")  # type: ignore[arg-type]


class TestTriggerTypeMapping:
    """Each TriggerType value maps correctly."""

    def test_eventbridge_schedule_maps_to_schedule(self) -> None:
        """EVENTBRIDGE_SCHEDULE maps to schedule."""
        result = map_trigger_type(EngTriggerType.EVENTBRIDGE_SCHEDULE)
        assert result == PkgTriggerType.SCHEDULE
        assert str(result) == "schedule"

    def test_lambda_furl_maps_to_webhook(self) -> None:
        """LAMBDA_FURL maps to webhook."""
        result = map_trigger_type(EngTriggerType.LAMBDA_FURL)
        assert result == PkgTriggerType.WEBHOOK
        assert str(result) == "webhook"

    def test_manual_maps_to_manual(self) -> None:
        """MANUAL maps to manual."""
        result = map_trigger_type(EngTriggerType.MANUAL)
        assert result == PkgTriggerType.MANUAL
        assert str(result) == "manual"

    def test_unknown_trigger_type_raises(self) -> None:
        """Unrecognised trigger type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown TriggerType"):
            map_trigger_type("SNS_TOPIC")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Full conversion tests
# ---------------------------------------------------------------------------


def _make_output(
    *,
    lambda_artifacts: list[LambdaArtifact] | None = None,
    trigger_artifacts: list[TriggerArtifact] | None = None,
    credential_artifacts: list[CredentialArtifact] | None = None,
    conversion_report: dict | None = None,
) -> TranslationOutput:
    """Build a representative ``TranslationOutput``."""
    return TranslationOutput(
        state_machine={
            "QueryLanguage": "JSONata",
            "StartAt": "Process",
            "States": {"Process": {"Type": "Pass", "End": True}},
        },
        lambda_artifacts=lambda_artifacts or [],
        trigger_artifacts=trigger_artifacts or [],
        credential_artifacts=credential_artifacts or [],
        conversion_report=conversion_report
        or {
            "total_nodes": 3,
            "classification_breakdown": {"AWS_NATIVE": 2, "CODE_JS": 1},
            "confidence_score": 0.85,
        },
    )


class TestFullConversion:
    """End-to-end TranslationOutput -> PackagerInput conversion."""

    def test_representative_data(self) -> None:
        """Full conversion with lambdas, triggers, and credentials."""
        output = _make_output(
            lambda_artifacts=[
                LambdaArtifact(
                    function_name="process_data",
                    runtime=EngLambdaRuntime.PYTHON,
                    handler_code="def handler(event, context): pass",
                    dependencies=["httpx==0.27.0"],
                ),
                LambdaArtifact(
                    function_name="transform_js",
                    runtime=EngLambdaRuntime.NODEJS,
                    handler_code="exports.handler = async (event) => {};",
                ),
            ],
            trigger_artifacts=[
                TriggerArtifact(
                    trigger_type=EngTriggerType.EVENTBRIDGE_SCHEDULE,
                    config={"schedule_expression": "rate(5 minutes)"},
                ),
                TriggerArtifact(
                    trigger_type=EngTriggerType.LAMBDA_FURL,
                    config={"path": "/webhook"},
                    lambda_artifact=LambdaArtifact(
                        function_name="webhook_handler",
                        runtime=EngLambdaRuntime.NODEJS,
                        handler_code="exports.handler = async (event) => {};",
                    ),
                ),
            ],
            credential_artifacts=[
                CredentialArtifact(
                    parameter_path="/phaeton/credentials/slack",
                    credential_type="oauth2",
                    placeholder_value="<slack-token>",
                ),
            ],
            conversion_report={
                "total_nodes": 5,
                "classification_breakdown": {"AWS_NATIVE": 3, "CODE_JS": 2},
                "confidence_score": 0.85,
            },
        )

        result = convert_output_to_packager_input(output, "my-workflow")

        # Pydantic round-trip validation
        validated = PackagerInput.model_validate(result.model_dump())

        # Metadata
        assert validated.metadata.workflow_name == "my-workflow"
        assert validated.metadata.confidence_score == 0.85

        # State machine
        assert validated.state_machine.asl["StartAt"] == "Process"

        # Lambda functions
        assert len(validated.lambda_functions) == 2
        assert validated.lambda_functions[0].function_name == "process_data"
        assert validated.lambda_functions[0].runtime == PkgLambdaRuntime.PYTHON
        assert validated.lambda_functions[0].dependencies == ["httpx==0.27.0"]
        assert validated.lambda_functions[1].function_name == "transform_js"
        assert validated.lambda_functions[1].runtime == PkgLambdaRuntime.NODEJS

        # Triggers
        assert len(validated.triggers) == 2
        assert validated.triggers[0].trigger_type == PkgTriggerType.SCHEDULE
        assert validated.triggers[0].configuration == {
            "schedule_expression": "rate(5 minutes)"
        }
        assert validated.triggers[1].trigger_type == PkgTriggerType.WEBHOOK
        assert validated.triggers[1].associated_lambda_name == "webhook_handler"

        # Credentials
        assert len(validated.credentials) == 1
        assert validated.credentials[0].parameter_path == "/phaeton/credentials/slack"
        assert validated.credentials[0].credential_type == "oauth2"
        assert validated.credentials[0].placeholder_value == "<slack-token>"

        # Conversion report
        assert validated.conversion_report.total_nodes == 5
        assert validated.conversion_report.confidence_score == 0.85
        assert validated.conversion_report.classification_breakdown == {
            "AWS_NATIVE": 3,
            "CODE_JS": 2,
        }

    def test_empty_artifacts(self) -> None:
        """Empty artifacts produce empty lists in output."""
        output = _make_output()
        result = convert_output_to_packager_input(output, "empty-workflow")

        assert result.lambda_functions == []
        assert result.triggers == []
        assert result.credentials == []
        assert result.metadata.workflow_name == "empty-workflow"

    def test_credential_path_normalisation(self) -> None:
        """Paths missing a leading slash get one prepended."""
        output = _make_output(
            credential_artifacts=[
                CredentialArtifact(
                    parameter_path="phaeton/creds/api",
                    credential_type="api_key",
                ),
            ],
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.credentials[0].parameter_path == "/phaeton/creds/api"

    def test_confidence_score_normalisation_from_percentage(self) -> None:
        """Scores above 1.0 are treated as percentages and divided by 100."""
        output = _make_output(
            conversion_report={
                "total_nodes": 10,
                "confidence_score": 85.0,
            },
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.metadata.confidence_score == 0.85
        assert result.conversion_report.confidence_score == 0.85

    def test_confidence_score_already_normalised(self) -> None:
        """Scores in 0.0-1.0 range pass through unchanged."""
        output = _make_output(
            conversion_report={
                "total_nodes": 1,
                "confidence_score": 0.75,
            },
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.metadata.confidence_score == 0.75

    def test_manual_trigger(self) -> None:
        """Manual trigger maps correctly with no associated lambda."""
        output = _make_output(
            trigger_artifacts=[
                TriggerArtifact(
                    trigger_type=EngTriggerType.MANUAL,
                    config={},
                ),
            ],
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.triggers[0].trigger_type == PkgTriggerType.MANUAL
        assert result.triggers[0].associated_lambda_name is None


class TestFunctionTypeInference:
    """LambdaFunctionType is inferred from artifact metadata."""

    def test_python_defaults_to_code_node_python(self) -> None:
        """Python runtime defaults to CODE_NODE_PYTHON."""
        output = _make_output(
            lambda_artifacts=[
                LambdaArtifact(
                    function_name="my_func",
                    runtime=EngLambdaRuntime.PYTHON,
                    handler_code="def handler(): pass",
                ),
            ],
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.lambda_functions[0].function_type == LambdaFunctionType.CODE_NODE_PYTHON

    def test_nodejs_defaults_to_code_node_js(self) -> None:
        """Node.js runtime defaults to CODE_NODE_JS."""
        output = _make_output(
            lambda_artifacts=[
                LambdaArtifact(
                    function_name="my_func",
                    runtime=EngLambdaRuntime.NODEJS,
                    handler_code="exports.handler = () => {};",
                ),
            ],
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.lambda_functions[0].function_type == LambdaFunctionType.CODE_NODE_JS

    def test_webhook_name_infers_webhook_handler(self) -> None:
        """Function name containing 'webhook' infers WEBHOOK_HANDLER."""
        output = _make_output(
            lambda_artifacts=[
                LambdaArtifact(
                    function_name="webhook_handler",
                    runtime=EngLambdaRuntime.NODEJS,
                    handler_code="exports.handler = () => {};",
                ),
            ],
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.lambda_functions[0].function_type == LambdaFunctionType.WEBHOOK_HANDLER

    def test_picofun_name_infers_api_client(self) -> None:
        """Function name containing 'picofun' infers PICOFUN_API_CLIENT."""
        output = _make_output(
            lambda_artifacts=[
                LambdaArtifact(
                    function_name="picofun_slack",
                    runtime=EngLambdaRuntime.PYTHON,
                    handler_code="def handler(): pass",
                ),
            ],
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.lambda_functions[0].function_type == LambdaFunctionType.PICOFUN_API_CLIENT
