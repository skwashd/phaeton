"""Dev-only CLI for the n8n-to-sfn translation engine."""

import json
from pathlib import Path
from typing import Annotated

import typer
from phaeton_models.translator import WorkflowAnalysis

from n8n_to_sfn.handler import create_default_engine

app = typer.Typer(help="Translate n8n workflows to AWS Step Functions.")


@app.command()
def translate(
    input_path: Annotated[
        Path,
        typer.Argument(help="Path to a WorkflowAnalysis JSON file."),
    ],
    output_path: Annotated[
        Path,
        typer.Option("--output", "-o", help="Path to write the TranslationOutput JSON."),
    ] = Path("translation_output.json"),
) -> None:
    """Read a WorkflowAnalysis JSON file, translate it, and write the output."""
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    analysis = WorkflowAnalysis.model_validate(raw)

    engine = create_default_engine()
    output = engine.translate(analysis)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    typer.echo(f"Translation complete: {output_path}")
    report = output.conversion_report
    typer.echo(f"Total nodes: {report.get('total_nodes')}")
    typer.echo(f"Translated nodes: {report.get('translated_nodes')}")
    if output.warnings:
        typer.echo(f"Warnings: {len(output.warnings)}")
