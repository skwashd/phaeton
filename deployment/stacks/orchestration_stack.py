"""CDK stack for the pipeline orchestration via Step Functions."""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct


class OrchestrationStack(cdk.Stack):
    """
    Deploy the Adapter Lambda and Step Functions state machine.

    The state machine orchestrates the full conversion pipeline:
    Analyzer -> Adapter1 -> Translator -> Adapter2 -> Packager
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        analyzer_function: lambda_.IFunction,
        translator_function: lambda_.IFunction,
        packager_function: lambda_.IFunction,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        adapter_function = lambda_.Function(
            self,
            "AdapterFunction",
            function_name="phaeton-adapter",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset("functions/adapter"),
            memory_size=256,
            timeout=cdk.Duration.seconds(30),
        )

        self.state_machine = self._build_state_machine(
            analyzer_function=analyzer_function,
            adapter_function=adapter_function,
            translator_function=translator_function,
            packager_function=packager_function,
        )

    def _build_state_machine(
        self,
        *,
        analyzer_function: lambda_.IFunction,
        adapter_function: lambda_.IFunction,
        translator_function: lambda_.IFunction,
        packager_function: lambda_.IFunction,
    ) -> sfn.StateMachine:
        """Build the Step Functions state machine for the conversion pipeline."""
        fail_state = sfn.Fail(self, "PipelineFailed", cause="A pipeline step failed")

        # Step 1: Prepare the envelope
        prepare_input = sfn.Pass(
            self,
            "PrepareInput",
            parameters={
                "workflow_name.$": "$.workflow_name",
                "service_data": {
                    "workflow.$": "$.workflow",
                },
            },
        )

        # Step 2: Analyze Workflow
        analyze = tasks.LambdaInvoke(
            self,
            "AnalyzeWorkflow",
            lambda_function=analyzer_function,
            payload=sfn.TaskInput.from_json_path_at("$.service_data"),
            result_path="$.lambda_result",
            retry_on_service_exceptions=True,
        )
        analyze.add_catch(fail_state)

        reshape_after_analyze = sfn.Pass(
            self,
            "ReshapeAfterAnalyze",
            parameters={
                "workflow_name.$": "$.workflow_name",
                "service_data.$": "$.lambda_result.Payload",
            },
        )

        # Step 3: Adapt for Translation
        adapt_for_translation = tasks.LambdaInvoke(
            self,
            "AdaptForTranslation",
            lambda_function=adapter_function,
            payload=sfn.TaskInput.from_object(
                {
                    "operation": "analyzer_to_translator",
                    "payload.$": "$.service_data",
                }
            ),
            result_path="$.lambda_result",
            retry_on_service_exceptions=True,
        )
        adapt_for_translation.add_catch(fail_state)

        reshape_after_adapt1 = sfn.Pass(
            self,
            "ReshapeAfterAdapt1",
            parameters={
                "workflow_name.$": "$.workflow_name",
                "service_data.$": "$.lambda_result.Payload",
            },
        )

        # Step 4: Translate Workflow
        translate = tasks.LambdaInvoke(
            self,
            "TranslateWorkflow",
            lambda_function=translator_function,
            payload=sfn.TaskInput.from_json_path_at("$.service_data"),
            result_path="$.lambda_result",
            retry_on_service_exceptions=True,
        )
        translate.add_catch(fail_state)

        reshape_after_translate = sfn.Pass(
            self,
            "ReshapeAfterTranslate",
            parameters={
                "workflow_name.$": "$.workflow_name",
                "service_data.$": "$.lambda_result.Payload",
            },
        )

        # Step 5: Adapt for Packaging
        adapt_for_packaging = tasks.LambdaInvoke(
            self,
            "AdaptForPackaging",
            lambda_function=adapter_function,
            payload=sfn.TaskInput.from_object(
                {
                    "operation": "translator_to_packager",
                    "payload.$": "$.service_data",
                    "workflow_name.$": "$.workflow_name",
                }
            ),
            result_path="$.lambda_result",
            retry_on_service_exceptions=True,
        )
        adapt_for_packaging.add_catch(fail_state)

        reshape_after_adapt2 = sfn.Pass(
            self,
            "ReshapeAfterAdapt2",
            parameters={
                "workflow_name.$": "$.workflow_name",
                "service_data.$": "$.lambda_result.Payload",
            },
        )

        # Step 6: Package Workflow
        package = tasks.LambdaInvoke(
            self,
            "PackageWorkflow",
            lambda_function=packager_function,
            payload=sfn.TaskInput.from_json_path_at("$.service_data"),
            payload_response_only=True,
            retry_on_service_exceptions=True,
        )
        package.add_catch(fail_state)

        # Chain all steps
        definition = (
            prepare_input.next(analyze)
            .next(reshape_after_analyze)
            .next(adapt_for_translation)
            .next(reshape_after_adapt1)
            .next(translate)
            .next(reshape_after_translate)
            .next(adapt_for_packaging)
            .next(reshape_after_adapt2)
            .next(package)
        )

        return sfn.StateMachine(
            self,
            "PipelineStateMachine",
            state_machine_name="phaeton-conversion-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=cdk.Duration.minutes(30),
        )
