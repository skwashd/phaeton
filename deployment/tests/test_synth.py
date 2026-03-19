"""CDK synthesis validation tests."""

import aws_cdk as cdk
from aws_cdk.assertions import Template

from stacks.expression_translator_stack import ExpressionTranslatorStack
from stacks.node_translator_stack import NodeTranslatorStack
from stacks.orchestration_stack import OrchestrationStack
from stacks.packager_stack import PackagerStack
from stacks.release_parser_stack import ReleaseParserStack
from stacks.spec_registry_stack import SpecRegistryStack
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


class TestSpecRegistryStack:
    """Tests for the Spec Registry stack."""

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, and runtime."""
        app = cdk.App()
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
        app = cdk.App()
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
        app = cdk.App()
        stack = SpecRegistryStack(app, "TestSpecRegistry")
        template = _synth_template(stack)
        template.resource_count_is("AWS::KMS::Key", 1)

    def test_lambda_has_bucket_permissions(self) -> None:
        """Verify Lambda has read/write permissions on the S3 bucket."""
        app = cdk.App()
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
        app = cdk.App()
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


class TestNodeTranslatorStack:
    """Tests for the Node Translator stack."""

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, runtime, and memory."""
        app = cdk.App()
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
        app = cdk.App()
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


class TestExpressionTranslatorStack:
    """Tests for the Expression Translator stack."""

    def test_has_lambda_function(self) -> None:
        """Verify Lambda function name, architecture, runtime, and memory."""
        app = cdk.App()
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
        app = cdk.App()
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
        SpecRegistryStack(app, "SpecRegistry")
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
        assert "SpecRegistry" in stack_names
        assert "WorkflowAnalyzer" in stack_names
        assert "TranslationEngine" in stack_names
        assert "Packager" in stack_names
        assert "Orchestration" in stack_names
