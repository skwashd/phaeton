"""Report generators for MIGRATE.md, conversion reports, and README."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from n8n_to_sfn_packager.models.inputs import ConversionReport, PackagerInput
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition


class ReportWriter:
    """Generate documentation and reports for the packaged output."""

    def write_migrate_md(
        self,
        input_data: PackagerInput,
        ssm_params: list[SSMParameterDefinition],
        output_dir: Path,
    ) -> Path:
        """
        Generate MIGRATE.md with structured pre/post-deployment checklists.

        Args:
            input_data: The packager input.
            ssm_params: SSM parameter definitions.
            output_dir: Root output directory.

        Returns:
            Path to the written MIGRATE.md.

        """
        wf_name = input_data.metadata.workflow_name

        sections = [
            f"# Migration Guide: {wf_name}\n",
            "This document lists all manual actions required before and after deployment.\n",
            self._migrate_pre_deployment(input_data, ssm_params),
            self._migrate_deployment(),
            self._migrate_post_deployment(input_data),
        ]

        file_path = output_dir / "MIGRATE.md"
        file_path.write_text("\n".join(s for s in sections if s))
        return file_path

    @staticmethod
    def _migrate_pre_deployment(
        input_data: PackagerInput,
        ssm_params: list[SSMParameterDefinition],
    ) -> str:
        """Return pre-deployment sections for MIGRATE.md."""
        parts = ["## Pre-deployment\n"]

        if ssm_params:
            table_rows = [
                "### Populate SSM Parameters\n",
                "| Parameter Path | Description | Action |",
                "|---|---|---|",
            ]
            for param in ssm_params:
                table_rows.append(
                    f"| `{param.parameter_path}` | {param.description} "
                    f"| Replace `{param.placeholder_value}` with real value |",
                )
            table_rows.append("")
            parts.append("\n".join(table_rows))

        if input_data.sub_workflows:
            items = ["### Deploy Sub-workflows First\n"]
            for sw in input_data.sub_workflows:
                items.append(
                    f"- [ ] Convert and deploy **{sw.name}** (source: `{sw.source_workflow_file}`)",
                )
            items.append(
                "\nUpdate sub-workflow ARN parameters in `cdk/cdk.json` after deployment.\n",
            )
            parts.append("\n".join(items))

        report = input_data.conversion_report
        if report.ai_assisted_nodes:
            items = [
                "### Review AI-Translated Nodes\n",
                f"Confidence score: {report.confidence_score:.0%}\n",
            ]
            for node in report.ai_assisted_nodes:
                items.append(f"- [ ] Review **{node}** (AI-assisted translation)")
            items.append("")
            parts.append("\n".join(items))

        if report.payload_warnings:
            items = ["### Payload Size Warnings\n"]
            for warning in report.payload_warnings:
                items.append(f"- [ ] {warning}")
            items.append("")
            parts.append("\n".join(items))

        return "\n".join(parts)

    @staticmethod
    def _migrate_deployment() -> str:
        """Return deployment section for MIGRATE.md."""
        return textwrap.dedent("""\
            ## Deployment

            ```bash
            cd cdk/
            uv sync
            uv run cdk bootstrap   # if not already done
            uv run cdk deploy
            ```
        """)

    @staticmethod
    def _migrate_post_deployment(input_data: PackagerInput) -> str:
        """Return post-deployment sections for MIGRATE.md."""
        parts = ["## Post-deployment\n"]

        webhook_triggers = [
            t for t in input_data.triggers if t.trigger_type in ("webhook", "app_event")
        ]
        if webhook_triggers:
            items = ["### Configure Webhook URLs\n"]
            for trigger in webhook_triggers:
                lambda_name = trigger.associated_lambda_name or "unknown"
                path = trigger.configuration.get("path", "/")
                items.append(
                    f"- [ ] Register the function URL for `{lambda_name}` "
                    f"(path: `{path}`) in the external system",
                )
            items.append("")
            parts.append("\n".join(items))

        parts.append(
            textwrap.dedent("""\
            ### EventBridge Failure Notifications

            - [ ] Set up an SNS topic and email subscription for execution failure notifications

            ### Verify Deployment

            - [ ] Run a test execution via AWS Console with sample input
            - [ ] Review CloudWatch logs and X-Ray traces for the test execution

            ### Tighten IAM Permissions

            SDK integration resource ARNs use wildcard patterns (`*`). Review and tighten these to specific resource ARNs for production use.
        """)
        )

        return "\n".join(parts)

    def write_conversion_report_json(
        self,
        input_data: PackagerInput,
        output_dir: Path,
    ) -> Path:
        """
        Write the machine-readable conversion report.

        Args:
            input_data: The packager input.
            output_dir: Root output directory.

        Returns:
            Path to the written JSON report.

        """
        reports_dir = output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        report = {
            "metadata": {
                "converter_version": input_data.metadata.converter_version,
                "timestamp": input_data.metadata.timestamp,
                "source_n8n_version": input_data.metadata.source_n8n_version,
                "workflow_name": input_data.metadata.workflow_name,
            },
            "total_nodes": input_data.conversion_report.total_nodes,
            "classification_breakdown": input_data.conversion_report.classification_breakdown,
            "expression_breakdown": input_data.conversion_report.expression_breakdown,
            "unsupported_nodes": input_data.conversion_report.unsupported_nodes,
            "payload_warnings": input_data.conversion_report.payload_warnings,
            "confidence_score": input_data.conversion_report.confidence_score,
            "ai_assisted_nodes": input_data.conversion_report.ai_assisted_nodes,
        }

        file_path = reports_dir / "conversion_report.json"
        file_path.write_text(json.dumps(report, indent=2) + "\n")
        return file_path

    def write_conversion_report_md(
        self,
        input_data: PackagerInput,
        output_dir: Path,
    ) -> Path:
        """
        Write the human-readable conversion report.

        Args:
            input_data: The packager input.
            output_dir: Root output directory.

        Returns:
            Path to the written Markdown report.

        """
        reports_dir = output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        r = input_data.conversion_report
        sections = [
            f"# Conversion Report: {input_data.metadata.workflow_name}\n",
            self._report_overview(input_data, r),
            self._report_breakdowns(r),
            self._report_warnings_and_recommendations(r),
        ]

        file_path = reports_dir / "conversion_report.md"
        file_path.write_text("\n".join(s for s in sections if s))
        return file_path

    @staticmethod
    def _report_overview(
        input_data: PackagerInput,
        r: ConversionReport,
    ) -> str:
        """Return overview section for the conversion report."""
        return textwrap.dedent(f"""\
            ## Overview

            - **Total nodes**: {r.total_nodes}
            - **Confidence score**: {r.confidence_score:.0%}
            - **Source n8n version**: {input_data.metadata.source_n8n_version}
            - **Converter version**: {input_data.metadata.converter_version}
        """)

    @staticmethod
    def _report_breakdowns(r: ConversionReport) -> str:
        """Return classification and expression breakdown sections."""
        parts = ["## Node Classification Breakdown\n"]
        if r.classification_breakdown:
            rows = ["| Category | Count |", "|---|---|"]
            for category, count in sorted(r.classification_breakdown.items()):
                rows.append(f"| {category} | {count} |")
            rows.append("")
            parts.append("\n".join(rows))
        else:
            parts.append("No classification data available.\n")

        parts.append("## Expression Translation Summary\n")
        if r.expression_breakdown:
            rows = ["| Type | Count |", "|---|---|"]
            for expr_type, count in sorted(r.expression_breakdown.items()):
                rows.append(f"| {expr_type} | {count} |")
            rows.append("")
            parts.append("\n".join(rows))
        else:
            parts.append("No expression data available.\n")

        return "\n".join(parts)

    @staticmethod
    def _report_warnings_and_recommendations(r: ConversionReport) -> str:
        """Return warnings, AI nodes, unsupported, and recommendations sections."""
        parts = ["## Warnings\n"]
        if r.payload_warnings:
            items = [f"- {w}" for w in r.payload_warnings]
            items.append("")
            parts.append("\n".join(items))
        else:
            parts.append("No warnings.\n")

        parts.append("## AI-Assisted Translations\n")
        if r.ai_assisted_nodes:
            items = [
                f"- **{node}** -- review recommended" for node in r.ai_assisted_nodes
            ]
            items.append("")
            parts.append("\n".join(items))
        else:
            parts.append("No AI-assisted translations.\n")

        if r.unsupported_nodes:
            items = ["## Unsupported Nodes\n"]
            items.extend(f"- {node}" for node in r.unsupported_nodes)
            items.append("")
            parts.append("\n".join(items))

        parts.append("## Recommendations\n")
        if r.confidence_score >= 0.9:
            parts.append(
                "High confidence conversion. Proceed with standard review.\n",
            )
        elif r.confidence_score >= 0.7:
            parts.append(
                "Moderate confidence. Review AI-assisted nodes carefully before deployment.\n",
            )
        else:
            parts.append(
                "Low confidence. Significant manual review required before deployment.\n",
            )

        return "\n".join(parts)

    def write_readme(self, input_data: PackagerInput, output_dir: Path) -> Path:
        """
        Write the README.md for the generated package.

        Args:
            input_data: The packager input.
            output_dir: Root output directory.

        Returns:
            Path to the written README.md.

        """
        wf_name = input_data.metadata.workflow_name
        content = textwrap.dedent(f"""\
            # {wf_name} -- Step Functions Package

            This package was generated by the n8n-to-Step-Functions converter.

            ## Contents

            - `cdk/` -- CDK application for deployment
            - `statemachine/` -- ASL state machine definition
            - `lambdas/` -- Lambda function source code
            - `reports/` -- Conversion reports
            - `MIGRATE.md` -- Migration checklist

            ## Quickstart

            1. Read `MIGRATE.md` and complete the pre-deployment steps.
            2. Deploy:

            ```bash
            cd cdk/
            uv sync
            uv run cdk bootstrap   # if not already done
            uv run cdk deploy
            ```

            3. Complete the post-deployment steps in `MIGRATE.md`.
        """)

        file_path = output_dir / "README.md"
        file_path.write_text(content)
        return file_path
