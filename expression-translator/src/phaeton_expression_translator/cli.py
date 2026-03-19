"""Dev-only Typer CLI for testing expression translation locally."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer()


@app.callback()
def _callback(
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Enable verbose logging.")
    ] = False,
) -> None:
    """Expression Translator CLI — translate n8n expressions to JSONata."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )


@app.command()
def translate(
    request_file: Annotated[
        Path,
        typer.Argument(
            help="Path to a JSON file with an ExpressionTranslationRequest."
        ),
    ],
) -> None:
    """Translate an n8n expression to JSONata using the AI agent."""
    from phaeton_expression_translator.agent import translate_expression
    from phaeton_expression_translator.models import ExpressionTranslationRequest

    if not request_file.exists():
        typer.echo(f"Error: file not found: {request_file}")
        raise typer.Exit(1)

    try:
        raw = json.loads(request_file.read_text())
        request = ExpressionTranslationRequest.model_validate(raw)
    except (json.JSONDecodeError, Exception) as exc:
        typer.echo(f"Error: invalid request file: {exc}")
        raise typer.Exit(1) from exc

    result = translate_expression(request)
    typer.echo(result.model_dump_json(indent=2))


def main() -> None:
    """Entry point wrapper for the CLI."""
    app()
