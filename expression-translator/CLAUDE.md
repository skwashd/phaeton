# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview and architecture.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/expression_translator/`
- **Lambda handler:** `expression_translator.handler:handler`
- **Dev CLI entry point:** `expression_translator.cli:app` (Typer — dev/testing only, not deployed)

## Component purpose

AI-powered expression translator that converts n8n expressions into JSONata expressions for use in AWS Step Functions, using Strands Agents and Amazon Bedrock.

## Key modules

- `handler.py` — Lambda entry point. Validates `ExpressionTranslationRequest`, invokes agent, returns structured response.
- `agent.py` — Strands Agent configuration and prompt templates. Handles n8n expression patterns, JSONata translation rules, and response parsing.
- `models.py` — Pydantic models (`ExpressionTranslationRequest`, `ExpressionTranslationResponse`). All models use `frozen=True`.
- `cli.py` — Dev-only Typer CLI for local testing. Not bundled in Lambda deployments.

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`cli.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
- The Strands Agent is created as a singleton via `_get_agent()` to reuse across warm Lambda invocations.
