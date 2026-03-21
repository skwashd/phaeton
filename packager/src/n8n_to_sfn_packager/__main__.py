"""CLI entry point for the Packager."""

from pathlib import Path

import typer

from n8n_to_sfn_packager.models.inputs import PackagerInput
from n8n_to_sfn_packager.packager import Packager, PackagerError

app = typer.Typer(help="n8n-to-sfn Packager: generate deployable CDK applications.")


@app.command()
def main(
    input_file: Path = typer.Option(  # noqa: B008
        ...,
        "--input",
        "-i",
        help="Path to the PackagerInput JSON file.",
        exists=True,
        readable=True,
    ),
    output_dir: Path = typer.Option(  # noqa: B008
        Path("./output"),
        "--output",
        "-o",
        help="Output directory for the generated package.",
    ),
    schema_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--schema",
        help="Path to the ASL JSON Schema (optional).",
    ),
) -> None:
    """Package a translated n8n workflow into a deployable CDK application."""
    json_text = input_file.read_text()
    input_data = PackagerInput.model_validate_json(json_text)

    typer.echo(f"Packaging workflow: {input_data.metadata.workflow_name}")
    typer.echo(f"Output directory: {output_dir}")

    packager = Packager(schema_path=schema_path)
    try:
        packager.package(input_data, output_dir)
    except PackagerError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e

    typer.echo("Packaging complete!")
    typer.echo(f"  State machine: {output_dir}/statemachine/definition.asl.json")
    typer.echo(f"  Lambda functions: {output_dir}/lambdas/")
    typer.echo(f"  CDK application: {output_dir}/cdk/")
    typer.echo(f"  Migration guide: {output_dir}/MIGRATE.md")


if __name__ == "__main__":
    app()
