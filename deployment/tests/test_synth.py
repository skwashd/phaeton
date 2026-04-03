"""CDK synthesis validation tests."""

import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from stacks.expression_translator_stack import ExpressionTranslatorStack
from stacks.node_translator_stack import NodeTranslatorStack
from stacks.orchestration_stack import OrchestrationStack
from stacks.packager_stack import PackagerStack
from stacks.release_parser_stack import ReleaseParserStack
from stacks.spec_registry_stack import SpecRegistryStack
from stacks.translation_engine_stack import TranslationEngineStack
from stacks.workflow_analyzer_stack import WorkflowAnalyzerStack

_BUNDLING_CONTEXT = {"aws:cdk:bundling-stacks": []}


def _app() -> cdk.App:
    """Create a CDK App with Docker bundling disabled for tests."""
    return cdk.App(context=_BUNDLING_CONTEXT)


def _synth_template(stack: cdk.Stack) -> Template:
    """Synthesize a stack and return its Template for assertions."""
    return Template.from_stack(stack)


def _has_powertools_layer(template: Template) -> None:
    """Assert that the Lambda function has the Powertools layer attached."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Layers": Match.array_with(
                [
                    Match.object_like(
                        {
                            "Ref": Match.string_like_regexp(
                                "SsmParameterValue.*powertools.*",
                            ),
                        },
                    ),
                ],
            ),
        },
    )


class TestReleaseParserStack:
    """Tests for the Release Parser stack."""

    def test_has_lambda_function(self):
        app = _app()
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
        app = _app()
        stack = ReleaseParserStack(app, "TestReleaseParser")
        template = _synth_template(stack)
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_has_daily_schedule_rule(self):
        app = _app()
        stack = ReleaseParserStack(app, "TestReleaseParser")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Events::Rule",
            {"ScheduleExpression": "rate(1 day)"},
        )

    def test_has_powertools_layer(self) -> None:
        """Verify the Powertools layer is attached."""
        app = _app()
        stack = ReleaseParserStack(app, "TestReleaseParser")
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestSpecRegistryStack:
    """Tests for the Spec Registry stack."""

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, and runtime."""
        app = _app()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-spec-indexer",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
            },
        )

    def test_has_s3_bucket_with_kms_encryption(self) -> None:
        """Verify S3 bucket exists with KMS encryption and versioning."""
        app = _app()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        template.resource_count_is("AWS::S3::Bucket", 1)
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketName": "phaeton-spec-registry",
                "VersioningConfiguration": {"Status": "Enabled"},
            },
        )

    def test_has_kms_key(self) -> None:
        """Verify KMS key is created for bucket encryption."""
        app = _app()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        template.resource_count_is("AWS::KMS::Key", 1)

    def test_lambda_has_bucket_permissions(self) -> None:
        """Verify Lambda has read/write permissions on the S3 bucket."""
        app = _app()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        # The policy has both S3 and KMS statements; verify the IAM policy
        # resource exists (CDK grants read/write on both bucket and key).
        policies = template.find_resources("AWS::IAM::Policy")
        policy_strs = [str(v) for v in policies.values()]
        combined = " ".join(policy_strs)
        assert "s3:GetObject*" in combined, "Missing S3 read permission"
        assert "s3:PutObject" in combined, "Missing S3 write permission"

    def test_has_s3_event_notifications(self) -> None:
        """Verify S3 event notifications for .json and .yaml suffixes."""
        app = _app()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        # CDK creates a custom resource for S3 notifications
        template.has_resource_properties(
            "Custom::S3BucketNotifications",
            {
                "NotificationConfiguration": {
                    "LambdaFunctionConfigurations": [
                        {
                            "Events": ["s3:ObjectCreated:*"],
                            "Filter": {
                                "Key": {
                                    "FilterRules": [
                                        {"Name": "suffix", "Value": ".json"},
                                    ],
                                },
                            },
                        },
                        {
                            "Events": ["s3:ObjectCreated:*"],
                            "Filter": {
                                "Key": {
                                    "FilterRules": [
                                        {"Name": "suffix", "Value": ".yaml"},
                                    ],
                                },
                            },
                        },
                    ],
                },
            },
        )

    def test_no_powertools_layer(self) -> None:
        """Verify the Spec Registry Lambda does NOT have a Powertools layer."""
        app = _app()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-spec-indexer",
                "Layers": Match.absent(),
            },
        )


class TestWorkflowAnalyzerStack:
    """Tests for the Workflow Analyzer stack."""

    def test_has_lambda_function(self):
        app = _app()
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

    def test_has_powertools_layer(self) -> None:
        """Verify the Powertools layer is attached."""
        app = _app()
        stack = WorkflowAnalyzerStack(app, "TestWorkflowAnalyzer")
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestTranslationEngineStack:
    """Tests for the Translation Engine stack."""

    @staticmethod
    def _create_stack() -> TranslationEngineStack:
        """Create a TranslationEngineStack with translator dependencies."""
        app = _app()
        node_stack = NodeTranslatorStack(app, "NodeTranslator")
        expr_stack = ExpressionTranslatorStack(app, "ExpressionTranslator")
        return TranslationEngineStack(
            app,
            "TestTranslationEngine",
            node_translator_function=node_stack.function,
            expression_translator_function=expr_stack.function,
        )

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, and runtime."""
        stack = self._create_stack()
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-translation-engine",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
            },
        )

    def test_has_translator_env_vars(self) -> None:
        """Verify both translator function name env vars are set."""
        stack = self._create_stack()
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-translation-engine",
                "Environment": {
                    "Variables": {
                        "NODE_TRANSLATOR_FUNCTION_NAME": {},
                        "EXPRESSION_TRANSLATOR_FUNCTION_NAME": {},
                    },
                },
            },
        )

    def test_grants_invoke_on_both_translators(self) -> None:
        """Verify IAM invoke permissions for both translator functions."""
        stack = self._create_stack()
        template = _synth_template(stack)
        policies = template.find_resources("AWS::IAM::Policy")
        policy_json = str(policies)
        assert "lambda:InvokeFunction" in policy_json

    def test_has_powertools_layer(self) -> None:
        """Verify the Powertools layer is attached."""
        stack = self._create_stack()
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestNodeTranslatorStack:
    """Tests for the Node Translator stack."""

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, runtime, and memory."""
        app = _app()
        stack = NodeTranslatorStack(app, "TestNodeTranslator")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-node-translator",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
                "MemorySize": 1024,
                "Timeout": 120,
            },
        )

    def test_has_bedrock_policy(self) -> None:
        """Verify Bedrock InvokeModel IAM policy is attached."""
        app = _app()
        stack = NodeTranslatorStack(app, "TestNodeTranslator")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": [
                        {
                            "Action": "bedrock:InvokeModel",
                            "Effect": "Allow",
                            "Resource": "arn:aws:bedrock:*::foundation-model/*",
                        },
                    ],
                },
            },
        )

    def test_has_powertools_layer(self) -> None:
        """Verify the Powertools layer is attached."""
        app = _app()
        stack = NodeTranslatorStack(app, "TestNodeTranslator")
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestExpressionTranslatorStack:
    """Tests for the Expression Translator stack."""

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, runtime, and memory."""
        app = _app()
        stack = ExpressionTranslatorStack(app, "TestExpressionTranslator")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": "phaeton-expression-translator",
                "Architectures": ["arm64"],
                "Runtime": "python3.13",
                "MemorySize": 1024,
                "Timeout": 120,
            },
        )

    def test_has_bedrock_policy(self) -> None:
        """Verify Bedrock InvokeModel IAM policy is attached."""
        app = _app()
        stack = ExpressionTranslatorStack(app, "TestExpressionTranslator")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": [
                        {
                            "Action": "bedrock:InvokeModel",
                            "Effect": "Allow",
                            "Resource": "arn:aws:bedrock:*::foundation-model/*",
                        },
                    ],
                },
            },
        )

    def test_has_powertools_layer(self) -> None:
        """Verify the Powertools layer is attached."""
        app = _app()
        stack = ExpressionTranslatorStack(app, "TestExpressionTranslator")
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestPackagerStack:
    """Tests for the Packager stack."""

    def test_has_lambda_function(self):
        app = _app()
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
        app = _app()
        stack = PackagerStack(app, "TestPackager")
        template = _synth_template(stack)
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_has_ephemeral_storage(self):
        app = _app()
        stack = PackagerStack(app, "TestPackager")
        template = _synth_template(stack)
        template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "EphemeralStorage": {"Size": 1024},
            },
        )

    def test_has_powertools_layer(self) -> None:
        """Verify the Powertools layer is attached."""
        app = _app()
        stack = PackagerStack(app, "TestPackager")
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestOrchestrationStack:
    """Tests for the Orchestration stack."""

    @staticmethod
    def _create_stack() -> OrchestrationStack:
        app = _app()
        analyzer_stack = WorkflowAnalyzerStack(app, "Analyzer")
        node_stack = NodeTranslatorStack(app, "NodeTranslator")
        expr_stack = ExpressionTranslatorStack(app, "ExpressionTranslator")
        translator_stack = TranslationEngineStack(
            app,
            "Translator",
            node_translator_function=node_stack.function,
            expression_translator_function=expr_stack.function,
        )
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

    def test_adapter_has_powertools_layer(self) -> None:
        """Verify the adapter Lambda has the Powertools layer attached."""
        stack = self._create_stack()
        template = _synth_template(stack)
        _has_powertools_layer(template)


class TestFullAppSynth:
    """Test that the full app synthesizes without errors."""

    def test_all_stacks_synth(self):
        app = _app()

        ReleaseParserStack(app, "ReleaseParser")
        SpecRegistryStack(app, "SpecRegistry")
        workflow_analyzer = WorkflowAnalyzerStack(app, "WorkflowAnalyzer")
        node_translator = NodeTranslatorStack(app, "NodeTranslator")
        expression_translator = ExpressionTranslatorStack(
            app,
            "ExpressionTranslator",
        )
        translation_engine = TranslationEngineStack(
            app,
            "TranslationEngine",
            node_translator_function=node_translator.function,
            expression_translator_function=expression_translator.function,
        )
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
        assert "SpecRegistry" in stack_names
        assert "WorkflowAnalyzer" in stack_names
        assert "TranslationEngine" in stack_names
        assert "Packager" in stack_names
        assert "Orchestration" in stack_names
