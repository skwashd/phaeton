# CLAUDE.md

See the [top-level CLAUDE.md](../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

See [README.md](README.md) for project overview and architecture.

## Quick reference

- **Build system:** uv_build
- **Source layout:** `src/node_translator/`
- **Lambda handler:** `node_translator.handler:handler`
- **Dev CLI entry point:** `node_translator.cli:app` (Typer — dev/testing only, not deployed)

## Component purpose

AI-powered node translator that converts individual n8n workflow nodes into AWS Step Functions ASL states using Strands Agents and Amazon Bedrock.

## Key modules

- `handler.py` — Lambda entry point. Validates `NodeTranslationRequest`, invokes agent, returns structured response.
- `agent.py` — Strands Agent configuration and prompt templates. Manages Bedrock model interaction, JSON response parsing, and ASL state validation.
- `models.py` — Pydantic models (`NodeTranslationRequest`, `NodeTranslationResponse`). All models use `frozen=True`.
- `cli.py` — Dev-only Typer CLI for local testing. Not bundled in Lambda deployments.

## Code conventions

- The Lambda handler (`handler.py`) is the primary interface for this component.
- The CLI (`cli.py`) is a dev/testing adapter only and is not included in Lambda deployments. Typer is a dev dependency.
- The Strands Agent is created as a singleton via `_get_agent()` to reuse across warm Lambda invocations.
