"""
PicoFun artifact writer.

Generates PicoFun-specific packaging artifacts: a picorun Lambda layer
directory and a CDK construct file defining all PicoFun Lambda functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from picofun.config import Config
from picofun.layer import Layer
from picofun.template import Template

from n8n_to_sfn_packager.models.inputs import LambdaFunctionSpec


@dataclass(frozen=True)
class PicoFunOutput:
    """Metadata from PicoFun artifact generation."""

    layer_dir: Path
    construct_file: Path


def _create_config(output_dir: Path) -> Config:
    """
    Create a PicoFun Config with defaults, bypassing TOML file requirement.

    Args:
        output_dir: Target directory for generated artifacts.

    Returns:
        Configured PicoFun Config instance.

    """
    config: Config = Config.__new__(Config)
    config.set_defaults()
    config.output_dir = str(output_dir)
    return config


class PicoFunWriter:
    """
    Generates PicoFun-specific packaging artifacts.

    Creates a picorun Lambda layer directory and a CDK construct file
    for all PicoFun-generated Lambda functions.
    """

    def write(
        self,
        picofun_functions: list[LambdaFunctionSpec],
        namespace: str,
        output_dir: Path,
    ) -> PicoFunOutput:
        """
        Generate picorun layer and CDK construct file.

        Args:
            picofun_functions: PicoFun Lambda function specifications.
            namespace: Lambda function namespace prefix.
            output_dir: Root output directory for generated artifacts.

        Returns:
            PicoFunOutput with paths to the generated layer and construct file.

        """
        picofun_dir = output_dir / "picofun_layer"
        picofun_dir.mkdir(parents=True, exist_ok=True)

        config = _create_config(picofun_dir)
        Layer(config).prepare()
        layer_dir = picofun_dir / "layer"

        lambda_names = [spec.function_name for spec in picofun_functions]
        template = Template(config.template_path)

        from picofun.terraform_generator import TerraformGenerator

        generator = TerraformGenerator(template, namespace, config)
        generator.generate(lambda_names)

        construct_file = picofun_dir / "main.tf"

        return PicoFunOutput(layer_dir=layer_dir, construct_file=construct_file)
