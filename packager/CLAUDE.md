# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview and architecture.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/n8n_to_sfn_packager/`
- **Lambda handler:** `n8n_to_sfn_packager.handler:handler`
- **Dev CLI entry point:** `python -m n8n_to_sfn_packager` (Typer — dev/testing only, not deployed)

## Component purpose

Generates deployable CDK applications from translated n8n workflows. Accepts a `PackagerInput` payload containing ASL definitions and Lambda code, writes out a complete CDK project with state machine definitions, Lambda functions, IAM policies, and SSM parameters.

## Key modules

- `handler.py` — Lambda entry point. Validates `PackagerInput`, runs packaging, zips output, uploads to S3.
- `packager.py` — Core `Packager` orchestrator. Coordinates all writers to produce the output directory.
- `models/inputs.py` — `PackagerInput` Pydantic model. All models use `frozen=True`.
- `models/ssm.py` — SSM parameter models.
- `writers/` — Output generators:
  - `asl_writer.py` — Writes ASL state machine definitions.
  - `cdk_writer.py` — Generates CDK application code.
  - `lambda_writer.py` — Writes Lambda function code.
  - `iam_writer.py` — Generates IAM policy documents.
  - `ssm_writer.py` — Writes SSM parameter definitions.
  - `report_writer.py` — Generates migration guide.
- `__main__.py` — Dev-only Typer CLI entry point. Not bundled in Lambda deployments.

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`__main__.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
- Generated CDK code must use stable `aws_cdk.aws_lambda` constructs, never `aws_cdk.aws_lambda_python_alpha`.
