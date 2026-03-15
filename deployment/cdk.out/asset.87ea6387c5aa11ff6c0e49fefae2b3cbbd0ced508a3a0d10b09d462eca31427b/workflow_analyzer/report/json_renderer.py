"""Renders a ConversionReport as JSON."""

from phaeton_models.analyzer import ConversionReport


def render(report: ConversionReport) -> str:
    """Render a ConversionReport as an indented JSON string."""
    return report.model_dump_json(indent=2)
