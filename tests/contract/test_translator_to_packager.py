"""
Contract tests: Component 3 (Translator) -> Component 4 (Packager).

Verifies that TranslationOutput can be deserialized by the adapter and
converted to a valid PackagerInput, covering:
- JSON round-trip serialization across the boundary
- LambdaRuntime and TriggerType enum value mappings
- Field name and structural transformations
- Confidence score normalization
- Credential path normalization
"""

from __future__ import annotations

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
    TranslationOutput,
)
from phaeton_models.translator_output import (
    LambdaRuntime as EngLambdaRuntime,
)
from phaeton_models.translator_output import (
    TriggerType as EngTriggerType,
)


class TestJsonRoundTrip:
    """TranslationOutput survives JSON serialization across the boundary."""

    def test_output_serializes_and_adapter_accepts(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Serialize output to JSON, deserialize, then convert via adapter."""
        json_data = sample_translation_output.model_dump(mode="json")
        restored = TranslationOutput.model_validate(json_data)
        result = convert_output_to_packager_input(restored, "test-workflow")
        assert isinstance(result, PackagerInput)

    def test_output_json_string_round_trip(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Verify JSON string serialization fidelity."""
        json_str = sample_translation_output.model_dump_json()
        restored = TranslationOutput.model_validate_json(json_str)
        result = convert_output_to_packager_input(restored, "test-workflow")
        assert isinstance(result, PackagerInput)
        assert len(result.lambda_functions) == len(
            sample_translation_output.lambda_artifacts,
        )

    def test_packager_input_is_itself_serializable(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """PackagerInput produced by adapter round-trips through JSON."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        json_data = result.model_dump(mode="json")
        restored = PackagerInput.model_validate(json_data)
        assert restored.metadata.workflow_name == "test-workflow"


class TestLambdaRuntimeEnumMapping:
    """LambdaRuntime enum values map correctly across the boundary."""

    def test_all_engine_runtimes_are_mapped(self) -> None:
        """Every EngLambdaRuntime value has a mapping to PkgLambdaRuntime."""
        for runtime in EngLambdaRuntime:
            mapped = map_runtime(runtime)
            assert isinstance(mapped, PkgLambdaRuntime)

    def test_python_maps_to_python(self) -> None:
        """PYTHON (uppercase) maps to python (lowercase)."""
        assert map_runtime(EngLambdaRuntime.PYTHON) == PkgLambdaRuntime.PYTHON

    def test_nodejs_maps_to_nodejs(self) -> None:
        """NODEJS (uppercase) maps to nodejs (lowercase)."""
        assert map_runtime(EngLambdaRuntime.NODEJS) == PkgLambdaRuntime.NODEJS

    def test_runtime_name_parity(self) -> None:
        """Both enums define the same runtime names."""
        eng_names = {r.name for r in EngLambdaRuntime}
        pkg_names = {r.name for r in PkgLambdaRuntime}
        assert eng_names == pkg_names


class TestTriggerTypeEnumMapping:
    """TriggerType enum values map correctly across the boundary."""

    def test_all_engine_trigger_types_are_mapped(self) -> None:
        """Every EngTriggerType value has a mapping to PkgTriggerType."""
        for tt in EngTriggerType:
            mapped = map_trigger_type(tt)
            assert isinstance(mapped, PkgTriggerType)

    def test_eventbridge_schedule_maps_to_schedule(self) -> None:
        """EVENTBRIDGE_SCHEDULE maps to SCHEDULE."""
        assert (
            map_trigger_type(EngTriggerType.EVENTBRIDGE_SCHEDULE)
            == PkgTriggerType.SCHEDULE
        )

    def test_lambda_furl_maps_to_webhook(self) -> None:
        """LAMBDA_FURL maps to WEBHOOK."""
        assert (
            map_trigger_type(EngTriggerType.LAMBDA_FURL) == PkgTriggerType.WEBHOOK
        )

    def test_manual_maps_to_manual(self) -> None:
        """MANUAL maps to MANUAL."""
        assert (
            map_trigger_type(EngTriggerType.MANUAL) == PkgTriggerType.MANUAL
        )


class TestLambdaConversion:
    """LambdaArtifact converts to LambdaFunctionSpec with correct types."""

    def test_lambda_artifacts_converted(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """All lambda artifacts become lambda function specs."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        assert len(result.lambda_functions) == len(
            sample_translation_output.lambda_artifacts,
        )

    def test_function_names_preserved(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Function names pass through unchanged."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        orig_names = [a.function_name for a in sample_translation_output.lambda_artifacts]
        conv_names = [f.function_name for f in result.lambda_functions]
        assert conv_names == orig_names

    def test_function_type_inference_webhook(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Function named 'webhook_handler' infers WEBHOOK_HANDLER type."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        fn_map = {f.function_name: f for f in result.lambda_functions}
        assert fn_map["webhook_handler"].function_type == LambdaFunctionType.WEBHOOK_HANDLER

    def test_function_type_inference_picofun(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Function named 'picofun_*' infers PICOFUN_API_CLIENT type."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        fn_map = {f.function_name: f for f in result.lambda_functions}
        assert (
            fn_map["picofun_slack_client"].function_type
            == LambdaFunctionType.PICOFUN_API_CLIENT
        )

    def test_dependencies_preserved(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Dependencies list passes through unchanged."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        fn_map = {f.function_name: f for f in result.lambda_functions}
        assert fn_map["transform_handler"].dependencies == ["aws-sdk"]


class TestTriggerConversion:
    """TriggerArtifact converts to TriggerSpec correctly."""

    def test_trigger_artifacts_converted(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """All trigger artifacts become trigger specs."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        assert len(result.triggers) == len(
            sample_translation_output.trigger_artifacts,
        )

    def test_trigger_types_mapped(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Trigger types use packager enum values."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        trigger_types = {t.trigger_type for t in result.triggers}
        assert PkgTriggerType.SCHEDULE in trigger_types
        assert PkgTriggerType.WEBHOOK in trigger_types
        assert PkgTriggerType.MANUAL in trigger_types

    def test_associated_lambda_name_set(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Trigger with lambda_artifact gets associated_lambda_name."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        webhook_triggers = [
            t for t in result.triggers if t.trigger_type == PkgTriggerType.WEBHOOK
        ]
        assert len(webhook_triggers) == 1
        assert webhook_triggers[0].associated_lambda_name == "webhook_handler"


class TestCredentialConversion:
    """CredentialArtifact converts to CredentialSpec correctly."""

    def test_credentials_converted(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """All credential artifacts become credential specs."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        assert len(result.credentials) == len(
            sample_translation_output.credential_artifacts,
        )

    def test_credential_path_normalised(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Credential paths always start with '/'."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        for cred in result.credentials:
            assert cred.parameter_path.startswith("/"), (
                f"parameter_path {cred.parameter_path!r} does not start with '/'"
            )

    def test_missing_slash_is_added(self) -> None:
        """A path without leading '/' gets one added by the adapter."""
        output = TranslationOutput(
            state_machine={"StartAt": "S1", "States": {}},
            credential_artifacts=[
                CredentialArtifact(
                    parameter_path="no/leading/slash",
                    credential_type="api_key",
                ),
            ],
            conversion_report={"confidence_score": 0.5, "total_nodes": 1},
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.credentials[0].parameter_path == "/no/leading/slash"


class TestConfidenceScoreNormalization:
    """Confidence scores normalize to 0.0-1.0 range."""

    def test_decimal_score_preserved(self) -> None:
        """Score already in 0.0-1.0 is unchanged."""
        output = TranslationOutput(
            state_machine={"StartAt": "S1", "States": {}},
            conversion_report={"confidence_score": 0.85, "total_nodes": 1},
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.metadata.confidence_score == 0.85

    def test_percentage_score_divided_by_100(self) -> None:
        """Score > 1.0 is treated as a percentage."""
        output = TranslationOutput(
            state_machine={"StartAt": "S1", "States": {}},
            conversion_report={"confidence_score": 85.0, "total_nodes": 1},
        )
        result = convert_output_to_packager_input(output, "test")
        assert result.metadata.confidence_score == 0.85


class TestMetadataMapping:
    """Conversion report metadata maps to WorkflowMetadata."""

    def test_workflow_name_set(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Workflow name from argument is used."""
        result = convert_output_to_packager_input(
            sample_translation_output, "my-workflow",
        )
        assert result.metadata.workflow_name == "my-workflow"

    def test_n8n_version_from_report(
        self, sample_translation_output: TranslationOutput,
    ) -> None:
        """Source n8n version comes from conversion_report dict."""
        result = convert_output_to_packager_input(
            sample_translation_output, "test-workflow",
        )
        assert result.metadata.source_n8n_version == "1.50.0"


class TestSchemaCompatibility:
    """JSON schemas are compatible across the boundary."""

    def test_translation_output_schema_has_required_fields(self) -> None:
        """TranslationOutput schema includes fields the adapter reads."""
        schema = TranslationOutput.model_json_schema()
        props = schema.get("properties", {})
        adapter_reads = [
            "state_machine",
            "lambda_artifacts",
            "trigger_artifacts",
            "credential_artifacts",
            "conversion_report",
        ]
        for field in adapter_reads:
            assert field in props, (
                f"TranslationOutput missing field {field!r}"
            )

    def test_packager_input_schema_covers_adapter_output(self) -> None:
        """PackagerInput schema matches what the adapter produces."""
        schema = PackagerInput.model_json_schema()
        required = schema.get("required", [])
        expected = ["metadata", "state_machine", "conversion_report"]
        for field in expected:
            assert field in required, (
                f"PackagerInput missing required field {field!r}"
            )
