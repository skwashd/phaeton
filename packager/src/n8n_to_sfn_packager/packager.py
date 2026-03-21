"""
Top-level Packager orchestrator.

Coordinates all writers to produce the complete deployable output
directory from a ``PackagerInput``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from n8n_to_sfn_packager.models.inputs import LambdaFunctionType, PackagerInput
from n8n_to_sfn_packager.writers.asl_writer import ASLWriter
from n8n_to_sfn_packager.writers.cdk_writer import CDKWriter
from n8n_to_sfn_packager.writers.iam_writer import IAMPolicyGenerator
from n8n_to_sfn_packager.writers.lambda_writer import LambdaWriter
from n8n_to_sfn_packager.writers.picofun_writer import PicoFunOutput, PicoFunWriter
from n8n_to_sfn_packager.writers.report_writer import ReportWriter
from n8n_to_sfn_packager.writers.ssm_writer import SSMWriter

logger = logging.getLogger(__name__)


class PackagerError(Exception):
    """Raised when the packaging pipeline fails."""


class Packager:
    """Orchestrate the full packaging pipeline."""

    def __init__(self, schema_path: Path | None = None) -> None:
        """
        Initialise with an optional ASL schema path override.

        Args:
            schema_path: Path to the ASL JSON Schema file.

        """
        self._asl_writer = ASLWriter(schema_path=schema_path)
        self._lambda_writer = LambdaWriter()
        self._ssm_writer = SSMWriter()
        self._iam_generator = IAMPolicyGenerator()
        self._picofun_writer = PicoFunWriter()
        self._cdk_writer = CDKWriter()
        self._report_writer = ReportWriter()

    def package(self, input_data: PackagerInput, output_dir: Path) -> Path:
        """
        Run the full packaging pipeline.

        Args:
            input_data: The packager input (inter-component contract).
            output_dir: Root output directory.

        Returns:
            Path to the output directory.

        Raises:
            PackagerError: If any step in the pipeline fails.

        """
        output_dir.mkdir(parents=True, exist_ok=True)

        self._step_validate_asl(input_data)
        self._step_write_asl(input_data, output_dir)
        self._step_write_lambdas(input_data, output_dir)
        picofun_output = self._step_write_picofun(input_data, output_dir)
        ssm_params = self._step_generate_ssm(input_data)
        iam_policy = self._step_generate_iam(input_data, ssm_params)
        webhook_warnings = self._step_write_cdk(
            input_data,
            iam_policy,
            ssm_params,
            output_dir,
            picofun_output,
        )
        if webhook_warnings:
            updated_report = input_data.conversion_report.model_copy(
                update={
                    "payload_warnings": [
                        *input_data.conversion_report.payload_warnings,
                        *webhook_warnings,
                    ],
                },
            )
            input_data = input_data.model_copy(
                update={"conversion_report": updated_report},
            )
        self._step_write_reports(input_data, ssm_params, output_dir)

        logger.info("Packaging complete: %s", output_dir)
        return output_dir

    def _step_validate_asl(self, input_data: PackagerInput) -> None:
        """Validate the ASL definition early."""
        errors = self._asl_writer.validate(input_data.state_machine.asl)
        if errors:
            msg = "ASL validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise PackagerError(msg)
        logger.info("ASL validation passed")

    def _step_write_asl(self, input_data: PackagerInput, output_dir: Path) -> None:
        """Write the ASL definition file."""
        self._asl_writer.write(input_data.state_machine, output_dir)
        logger.info("Wrote statemachine/definition.asl.json")

    def _step_write_lambdas(self, input_data: PackagerInput, output_dir: Path) -> None:
        """Write all Lambda function directories and shared dependency layers."""
        try:
            self._lambda_writer.write_all(input_data.lambda_functions, output_dir)
            for spec in input_data.lambda_functions:
                logger.info("Wrote Lambda: %s", spec.function_name)
        except Exception as e:
            msg = f"Failed to write Lambda functions: {e}"
            raise PackagerError(msg) from e

    def _step_write_picofun(
        self,
        input_data: PackagerInput,
        output_dir: Path,
    ) -> PicoFunOutput | None:
        """Generate PicoFun layer and CDK construct if PicoFun functions exist."""
        picofun_functions = [
            f
            for f in input_data.lambda_functions
            if f.function_type == LambdaFunctionType.PICOFUN_API_CLIENT
        ]
        if not picofun_functions:
            return None
        result = self._picofun_writer.write(
            picofun_functions=picofun_functions,
            namespace=input_data.metadata.workflow_name,
            output_dir=output_dir,
        )
        logger.info("Wrote PicoFun artifacts: %s", result.layer_dir)
        return result

    def _step_generate_ssm(self, input_data: PackagerInput) -> list:
        """Generate SSM parameter definitions."""
        ssm_params = self._ssm_writer.generate_parameter_definitions(
            input_data.credentials,
            input_data.oauth_credentials,
        )
        logger.info("Generated %d SSM parameter definitions", len(ssm_params))
        return ssm_params

    def _step_generate_iam(self, input_data: PackagerInput, ssm_params: list) -> dict:
        """Generate the IAM policy."""
        sub_arns = [
            f"arn:aws:states:*:*:stateMachine:{sw.name}"
            for sw in input_data.sub_workflows
        ]
        iam_policy = self._iam_generator.generate(
            asl_definition=input_data.state_machine.asl,
            lambda_specs=input_data.lambda_functions,
            ssm_parameters=ssm_params,
            kms_key_ref="${SharedStack.KmsKeyArn}",
            log_group_ref="${SharedStack.LogGroupArn}",
            sub_workflow_arns=sub_arns,
        )
        logger.info(
            "Generated IAM policy with %d statements", len(iam_policy["Statement"])
        )
        return iam_policy

    def _step_write_cdk(
        self,
        input_data: PackagerInput,
        iam_policy: dict,
        ssm_params: list,
        output_dir: Path,
        picofun_output: PicoFunOutput | None = None,
    ) -> list[str]:
        """
        Write the CDK application.

        Returns:
            Warnings about unauthenticated webhook handlers.

        """
        _, warnings = self._cdk_writer.write(
            input_data,
            iam_policy,
            ssm_params,
            output_dir,
            picofun_output=picofun_output,
        )
        for w in warnings:
            logger.warning(w)
        logger.info("Wrote CDK application")
        return warnings

    def _step_write_reports(
        self,
        input_data: PackagerInput,
        ssm_params: list,
        output_dir: Path,
    ) -> None:
        """Write all reports and documentation."""
        self._report_writer.write_migrate_md(input_data, ssm_params, output_dir)
        self._report_writer.write_conversion_report_json(input_data, output_dir)
        self._report_writer.write_conversion_report_md(input_data, output_dir)
        self._report_writer.write_readme(input_data, output_dir)
        logger.info("Wrote MIGRATE.md, reports, and README.md")
