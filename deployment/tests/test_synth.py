"""CDK synthesis validation tests."""

import aws_cdk as cdk
from aws_cdk.assertions import Template

from stacks.orchestration_stack import OrchestrationStack
from stacks.packager_stack import PackagerStack
from stacks.release_parser_stack import ReleaseParserStack
from stacks.translation_engine_stack import TranslationEngineStack
from stacks.workflow_analyzer_stack import WorkflowAnalyzerStack


def _synth_template(stack: cdk.Stack) -> Template:
    """Synthesize a stack and return its Template for assertions."""
    return Template.from_stack(stack)


class TestReleaseParserStack:
    """Tests for the Release Parser stack."""

    def test_has_lambda_function(self):
        app = cdk.App()
        stack = ReleaseParserStack(app, "TestReleaseParser")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-release-parser",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
            },
        )

    def test_has_s3_bucket(self):
        app = cdk.App()
        stack = ReleaseParserStack(app, "TestReleaseParser")
        template = _synth_template(stack)
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_has_daily_schedule_rule(self):
        app = cdk.App()
        stack = ReleaseParserStack(app, "TestReleaseParser")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Events::Rule",
            {"ScheduleExpression": "rate(1 day)"},
        )


class TestWorkflowAnalyzerStack:
    """Tests for the Workflow Analyzer stack."""

    def test_has_lambda_function(self):
        app = cdk.App()
        stack = WorkflowAnalyzerStack(app, "TestWorkflowAnalyzer")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-workflow-analyzer",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
            },
        )


class TestTranslationEngineStack:
    """Tests for the Translation Engine stack."""

    def test_has_lambda_function(self):
        app = cdk.App()
        stack = TranslationEngineStack(app, "TestTranslationEngine")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-translation-engine",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
            },
        )


class TestPackagerStack:
    """Tests for the Packager stack."""

    def test_has_lambda_function(self):
        app = cdk.App()
        stack = PackagerStack(app, "TestPackager")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-packager",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
                "MemorySize": 1024,
            },
        )

    def test_has_s3_bucket(self):
        app = cdk.App()
        stack = PackagerStack(app, "TestPackager")
        template = _synth_template(stack)
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_has_ephemeral_storage(self):
        app = cdk.App()
        stack = PackagerStack(app, "TestPackager")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "EphemeralStorage": {"Size": 1024},
            },
        )


class TestOrchestrationStack:
    """Tests for the Orchestration stack."""

    @staticmethod
    def _create_stack() -> OrchestrationStack:
        app = cdk.App()
        analyzer_stack = WorkflowAnalyzerStack(app, "Analyzer")
        translator_stack = TranslationEngineStack(app, "Translator")
        packager_stack = PackagerStack(app, "Packager")
        return OrchestrationStack(
            app,
            "TestOrchestration",
            analyzer_function=analyzer_stack.function,
            translator_function=translator_stack.function,
            packager_function=packager_stack.function,
        )

    def test_has_adapter_lambda(self):
        stack = self._create_stack()
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-adapter",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
            },
        )

    def test_has_state_machine(self):
        stack = self._create_stack()
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::StepFunctions::StateMachine",
            {
                "StateMachineName": "phaeton-conversion-pipeline",
            },
        )

    def test_state_machine_definition_references_steps(self):
        stack = self._create_stack()
        template = _synth_template(stack)
        # The DefinitionString is a Fn::Join intrinsic (contains Lambda ARN
        # refs), so we verify it contains the expected state names via the
        # raw template JSON rather than Match.serialized_json.
        sm_resources = template.find_resources("AWS::StepFunctions::StateMachine")
        assert len(sm_resources) == 1
        defn = next(iter(sm_resources.values()))
        defn_str = str(defn)
        for state_name in [
            "PrepareInput",
            "AnalyzeWorkflow",
            "TranslateWorkflow",
            "PackageWorkflow",
        ]:
            assert state_name in defn_str, f"Missing state {state_name}"


class TestFullAppSynth:
    """Test that the full app synthesizes without errors."""

    def test_all_stacks_synth(self):
        app = cdk.App()

        ReleaseParserStack(app, "ReleaseParser")
        workflow_analyzer = WorkflowAnalyzerStack(app, "WorkflowAnalyzer")
        translation_engine = TranslationEngineStack(app, "TranslationEngine")
        packager = PackagerStack(app, "Packager")
        OrchestrationStack(
            app,
            "Orchestration",
            analyzer_function=workflow_analyzer.function,
            translator_function=translation_engine.function,
            packager_function=packager.function,
        )

        # Verify all stacks synthesize without errors
        assembly = app.synth()
        stack_names = [s.stack_name for s in assembly.stacks]
        assert "ReleaseParser" in stack_names
        assert "WorkflowAnalyzer" in stack_names
        assert "TranslationEngine" in stack_names
        assert "Packager" in stack_names
        assert "Orchestration" in stack_names
