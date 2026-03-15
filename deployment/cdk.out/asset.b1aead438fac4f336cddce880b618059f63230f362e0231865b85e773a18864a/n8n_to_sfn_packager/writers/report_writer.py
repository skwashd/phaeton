"""Report generators for MIGRATE.md, conversion reports, and README."""

from __future__ import annotations

import json
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
        sections: list[str] = []
        wf_name = input_data.metadata.workflow_name

        sections.append(f"# Migration Guide: {wf_name}\n")
        sections.append(
            "This document lists all manual actions required before and after deployment.\n",
        )

        self._migrate_pre_deployment(sections, input_data, ssm_params)
        self._migrate_deployment(sections)
        self._migrate_post_deployment(sections, input_data)

        file_path = output_dir / "MIGRATE.md"
        file_path.write_text("\n".join(sections))
        return file_path

    def _migrate_pre_deployment(
        self,
        sections: list[str],
        input_data: PackagerInput,
        ssm_params: list[SSMParameterDefinition],
    ) -> None:
        """Append pre-deployment sections to the MIGRATE.md content."""
        sections.append("## Pre-deployment\n")

        if ssm_params:
            sections.append("### Populate SSM Parameters\n")
            sections.append("| Parameter Path | Description | Action |")
            sections.append("|---|---|---|")
            for param in ssm_params:
                sections.append(
                    f"| `{param.parameter_path}` | {param.description} "
                    f"| Replace `{param.placeholder_value}` with real value |",
                )
            sections.append("")

        if input_data.sub_workflows:
            sections.append("### Deploy Sub-workflows First\n")
            for sw in input_data.sub_workflows:
                sections.append(
                    f"- [ ] Convert and deploy **{sw.name}** (source: `{sw.source_workflow_file}`)",
                )
            sections.append(
                "\nUpdate sub-workflow ARN parameters in `cdk/cdk.json` after deployment.\n",
            )

        report = input_data.conversion_report
        if report.ai_assisted_nodes:
            sections.append("### Review AI-Translated Nodes\n")
            sections.append(f"Confidence score: {report.confidence_score:.0%}\n")
            for node in report.ai_assisted_nodes:
                sections.append(f"- [ ] Review **{node}** (AI-assisted translation)")
            sections.append("")

        if report.payload_warnings:
            sections.append("### Payload Size Warnings\n")
            for warning in report.payload_warnings:
                sections.append(f"- [ ] {warning}")
            sections.append("")

    @staticmethod
    def _migrate_deployment(sections: list[str]) -> None:
        """Append deployment section to the MIGRATE.md content."""
        sections.append("## Deployment\n")
        sections.append("```bash")
        sections.append("cd cdk/")
        sections.append("uv sync")
        sections.append("uv run cdk bootstrap   # if not already done")
        sections.append("uv run cdk deploy")
        sections.append("```\n")

    @staticmethod
    def _migrate_post_deployment(
        sections: list[str],
        input_data: PackagerInput,
    ) -> None:
        """Append post-deployment sections to the MIGRATE.md content."""
        sections.append("## Post-deployment\n")

        webhook_triggers = [
            t for t in input_data.triggers if t.trigger_type in ("webhook", "app_event")
        ]
        if webhook_triggers:
            sections.append("### Configure Webhook URLs\n")
            for trigger in webhook_triggers:
                lambda_name = trigger.associated_lambda_name or "unknown"
                path = trigger.configuration.get("path", "/")
                sections.append(
                    f"- [ ] Register the function URL for `{lambda_name}` "
                    f"(path: `{path}`) in the external system",
                )
            sections.append("")

        sections.append("### EventBridge Failure Notifications\n")
        sections.append(
            "- [ ] Set up an SNS topic and email subscription for execution failure notifications\n",
        )

        sections.append("### Verify Deployment\n")
        sections.append("- [ ] Run a test execution via AWS Console with sample input")
        sections.append(
            "- [ ] Review CloudWatch logs and X-Ray traces for the test execution\n",
        )

        sections.append("### Tighten IAM Permissions\n")
        sections.append(
            "SDK integration resource ARNs use wildcard patterns (`*`). "
            "Review and tighten these to specific resource ARNs for production use.\n",
        )

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
        sections: list[str] = []

        sections.append(
            f"# Conversion Report: {input_data.metadata.workflow_name}\n",
        )
        self._report_overview(sections, input_data, r)
        self._report_breakdowns(sections, r)
        self._report_warnings_and_recommendations(sections, r)

        file_path = reports_dir / "conversion_report.md"
        file_path.write_text("\n".join(sections))
        return file_path

    @staticmethod
    def _report_overview(
        sections: list[str],
        input_data: PackagerInput,
        r: ConversionReport,
    ) -> None:
        """Append overview section to the conversion report."""
        sections.append("## Overview\n")
        sections.append(f"- **Total nodes**: {r.total_nodes}")
        sections.append(f"- **Confidence score**: {r.confidence_score:.0%}")
        sections.append(
            f"- **Source n8n version**: {input_data.metadata.source_n8n_version}",
        )
        sections.append(
            f"- **Converter version**: {input_data.metadata.converter_version}\n",
        )

    @staticmethod
    def _report_breakdowns(sections: list[str], r: ConversionReport) -> None:
        """Append classification and expression breakdown sections."""
        sections.append("## Node Classification Breakdown\n")
        if r.classification_breakdown:
            sections.append("| Category | Count |")
            sections.append("|---|---|")
            for category, count in sorted(r.classification_breakdown.items()):
                sections.append(f"| {category} | {count} |")
            sections.append("")
        else:
            sections.append("No classification data available.\n")

        sections.append("## Expression Translation Summary\n")
        if r.expression_breakdown:
            sections.append("| Type | Count |")
            sections.append("|---|---|")
            for expr_type, count in sorted(r.expression_breakdown.items()):
                sections.append(f"| {expr_type} | {count} |")
            sections.append("")
        else:
            sections.append("No expression data available.\n")

    @staticmethod
    def _report_warnings_and_recommendations(
        sections: list[str],
        r: ConversionReport,
    ) -> None:
        """Append warnings, AI nodes, unsupported, and recommendations sections."""
        sections.append("## Warnings\n")
        if r.payload_warnings:
            for warning in r.payload_warnings:
                sections.append(f"- {warning}")
            sections.append("")
        else:
            sections.append("No warnings.\n")

        sections.append("## AI-Assisted Translations\n")
        if r.ai_assisted_nodes:
            for node in r.ai_assisted_nodes:
                sections.append(f"- **{node}** -- review recommended")
            sections.append("")
        else:
            sections.append("No AI-assisted translations.\n")

        if r.unsupported_nodes:
            sections.append("## Unsupported Nodes\n")
            for node in r.unsupported_nodes:
                sections.append(f"- {node}")
            sections.append("")

        sections.append("## Recommendations\n")
        if r.confidence_score >= 0.9:
            sections.append(
                "High confidence conversion. Proceed with standard review.\n",
            )
        elif r.confidence_score >= 0.7:
            sections.append(
                "Moderate confidence. Review AI-assisted nodes carefully before deployment.\n",
            )
        else:
            sections.append(
                "Low confidence. Significant manual review required before deployment.\n",
            )

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
        sections: list[str] = []

        sections.append(f"# {wf_name} -- Step Functions Package\n")
        sections.append(
            "This package was generated by the n8n-to-Step-Functions converter.\n",
        )

        sections.append("## Contents\n")
        sections.append("- `cdk/` -- CDK application for deployment")
        sections.append("- `statemachine/` -- ASL state machine definition")
        sections.append("- `lambdas/` -- Lambda function source code")
        sections.append("- `reports/` -- Conversion reports")
        sections.append("- `MIGRATE.md` -- Migration checklist\n")

        sections.append("## Quickstart\n")
        sections.append("1. Read `MIGRATE.md` and complete the pre-deployment steps.")
        sections.append("2. Deploy:")
        sections.append("")
        sections.append("```bash")
        sections.append("cd cdk/")
        sections.append("uv sync")
        sections.append("uv run cdk bootstrap   # if not already done")
        sections.append("uv run cdk deploy")
        sections.append("```\n")
        sections.append("3. Complete the post-deployment steps in `MIGRATE.md`.\n")

        file_path = output_dir / "README.md"
        file_path.write_text("\n".join(sections))
        return file_path
