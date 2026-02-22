"""CLI for the workflow analyzer."""

from pathlib import Path
from typing import Annotated

import typer

from workflow_analyzer.analyzer import WorkflowAnalyzer

app = typer.Typer(help="Analyze n8n workflows for AWS Step Functions conversion.")


@app.command()
def analyze(
    workflow_path: Annotated[
        Path,
        typer.Argument(help="Path to the n8n workflow JSON file."),
    ],
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", "-o", help="Directory to write reports to."),
    ] = Path("."),
    formats: Annotated[
        list[str] | None,
        typer.Option("--format", "-f", help="Report formats to generate."),
    ] = None,
    payload_limit: Annotated[
        int,
        typer.Option("--payload-limit", help="Payload limit in KiB."),
    ] = 256,
) -> None:
    """Analyze an n8n workflow and generate conversion feasibility reports."""
    if formats is None:
        formats = ["json", "md"]
    analyzer = WorkflowAnalyzer(payload_limit_kb=payload_limit)
    report = analyzer.analyze_and_render(workflow_path, output_dir, formats)

    typer.echo(f"Workflow: {report.source_workflow_name}")
    typer.echo(f"Confidence Score: {report.confidence_score}%")
    typer.echo(f"Total Nodes: {report.total_nodes}")
    typer.echo(f"Unsupported Nodes: {len(report.unsupported_nodes)}")

    if report.blocking_issues:
        typer.echo("\nBlocking Issues:")
        for issue in report.blocking_issues:
            typer.echo(f"  - {issue}")

    typer.echo(f"\nReports written to: {output_dir}")
