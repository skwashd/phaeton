"""Renders a ConversionReport as a Markdown document."""

from typing import Any

from workflow_analyzer.models.classification import NodeCategory
from workflow_analyzer.models.expression import ExpressionCategory
from workflow_analyzer.models.report import ConversionReport


def render(report: ConversionReport) -> str:
    """Render a ConversionReport as a Markdown string."""
    lines: list[str] = []
    _render_header(lines, report)
    _render_summary(lines, report)
    _render_node_classification(lines, report)
    _render_expression_analysis(lines, report)
    _render_payload_warnings(lines, report)
    _render_cross_node_references(lines, report)
    _render_api_clients(lines, report)
    _render_credentials(lines, report)
    _render_sub_workflows(lines, report)
    _render_recommendations(lines, report)
    return "\n".join(lines)


def _render_header(lines: list[str], report: ConversionReport) -> None:
    lines.append(f"# Conversion Feasibility Report: {report.source_workflow_name}")
    lines.append("")
    lines.append(f"**Analyzer version:** {report.analyzer_version}")
    lines.append(f"**Generated:** {report.timestamp.isoformat()}")
    lines.append(f"**Confidence Score:** {report.confidence_score}%")
    lines.append("")


def _render_summary(lines: list[str], report: ConversionReport) -> None:
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total nodes:** {report.total_nodes}")
    lines.append(f"- **Blocking issues:** {len(report.blocking_issues)}")
    for issue in report.blocking_issues:
        lines.append(f"  - {issue}")
    lines.append("")


def _render_node_classification(lines: list[str], report: ConversionReport) -> None:
    lines.append("## Node Classification")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for cat in NodeCategory:
        count = report.classification_summary.get(cat, 0)
        if count > 0:
            lines.append(f"| {cat.value} | {count} |")
    lines.append("")


def _render_expression_analysis(lines: list[str], report: ConversionReport) -> None:
    lines.append("## Expression Analysis")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for cat in ExpressionCategory:
        count = report.expression_summary.get(cat, 0)
        if count > 0:
            lines.append(f"| {cat.value} | {count} |")
    lines.append("")


def _render_payload_warnings(lines: list[str], report: ConversionReport) -> None:
    if not report.payload_warnings:
        return
    lines.append("## Payload Warnings")
    lines.append("")
    for pw in report.payload_warnings:
        lines.append(f"- **{pw.warning_type}** ({pw.severity}): {pw.description}")
        lines.append(f"  - *Recommendation:* {pw.recommendation}")
    lines.append("")


def _render_cross_node_references(lines: list[str], report: ConversionReport) -> None:
    if not report.cross_node_references:
        return
    lines.append("## Cross-Node References")
    lines.append("")
    lines.append("These references require Step Functions Variables for data passing:")
    lines.append("")
    for ref in report.cross_node_references:
        _render_single_ref(lines, ref)
    lines.append("")


def _render_single_ref(lines: list[str], ref: dict[str, Any]) -> None:
    lines.append(
        f"- `{ref['source_node_name']}` → `{ref['target_node_name']}` via `{ref['reference_pattern']}`"
    )


def _render_api_clients(lines: list[str], report: ConversionReport) -> None:
    if not report.required_picofun_clients:
        return
    lines.append("## Required API Clients")
    lines.append("")
    for client in report.required_picofun_clients:
        lines.append(f"- {client}")
    lines.append("")


def _render_credentials(lines: list[str], report: ConversionReport) -> None:
    if not report.required_credentials:
        return
    lines.append("## Required Credentials")
    lines.append("")
    lines.append("SSM parameters to populate:")
    lines.append("")
    for cred in report.required_credentials:
        lines.append(f"- `{cred}`")
    lines.append("")


def _render_sub_workflows(lines: list[str], report: ConversionReport) -> None:
    if not report.sub_workflows_detected:
        return
    lines.append("## Sub-Workflows")
    lines.append("")
    for sw in report.sub_workflows_detected:
        lines.append(f"- {sw}")
    lines.append("")


def _render_recommendations(lines: list[str], report: ConversionReport) -> None:
    lines.append("## Recommendations")
    lines.append("")
    if report.confidence_score >= 80:
        lines.append(
            "This workflow has a high confidence score and is a good candidate for automated conversion."
        )
    elif report.confidence_score >= 50:
        lines.append(
            "This workflow has a moderate confidence score. Some manual intervention may be required."
        )
    else:
        lines.append(
            "This workflow has a low confidence score. Significant manual intervention will be needed."
        )
    lines.append("")
