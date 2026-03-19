# Phaeton

Converts n8n workflows into deployable AWS Step Functions CDK applications.

## Overview

Phaeton is a managed pipeline that converts n8n workflow JSON exports into complete, deployable AWS CDK applications. Submit a workflow JSON, and Phaeton produces a zip archive containing an ASL state machine definition, Lambda functions, IAM policies, SSM credential placeholders, CDK infrastructure code, and a migration guide — ready to extract and deploy with `cdk deploy`.

The pipeline is deployed as AWS infrastructure (CDK stacks) with a Step Functions state machine (`phaeton-conversion-pipeline`) orchestrating the end-to-end conversion. It uses deterministic translation wherever possible and AI-powered translators (Bedrock + Claude Sonnet 4) as a fallback for complex node and expression conversions.

## Architecture

Phaeton is built as independent components, each with its own Lambda handler, codebase, and test suite. Components communicate only via well-defined contracts defined in phaeton-models. A Step Functions state machine orchestrates the pipeline stages sequentially:

```
n8n Workflow JSON
        │
        ▼
┌──────────────────────────────────────────────────┐
│  1. n8n Release Parser                           │
│  Versioned n8n node catalog, API spec matching   │
│  (~290 indexed API specs)                        │
└──────────────────────┬───────────────────────────┘
                       │  Node catalog
                       ▼
┌──────────────────────────────────────────────────┐
│  2. Workflow Analyzer                            │
│  Node classification, dependency graphs,         │
│  expression analysis, feasibility reports        │
└──────────────────────┬───────────────────────────┘
                       │  ConversionReport → WorkflowAnalysis
                       ▼
┌──────────────────────────────────────────────────┐
│  3. Translation Engine (n8n-to-sfn)              │
│  Deterministic ASL translation + AI translators  │
│  Lambda artifacts, trigger configs, variables    │
└──────────────────────┬───────────────────────────┘
                       │  TranslationOutput → PackagerInput
                       ▼
┌──────────────────────────────────────────────────┐
│  4. Packager                                     │
│  CDK app, ASL definition, Lambda code, IAM,      │
│  SSM params, MIGRATE.md, conversion reports      │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
               Zip Archive in S3
        (download → extract → cdk deploy)
```

## Project Structure

```
phaeton/end-to-end/
├── n8n-release-parser/      # Versioned n8n node catalog and API spec matching
├── workflow-analyzer/       # Workflow analysis and conversion feasibility reports
├── n8n-to-sfn/              # Translation engine: n8n workflows → ASL + Lambda artifacts
├── packager/                # CDK application generator from translation output
├── shared/phaeton-models/   # Shared Pydantic models and cross-component adapters
├── deployment/              # CDK deployment stacks for the Phaeton pipeline
├── node-translator/         # AI agent for n8n node → ASL state translation
├── expression-translator/   # AI agent for n8n expression → JSONata translation
├── spec-registry/           # API specification registry and indexer
├── docs/                    # Architecture plans & coding guidelines
│   └── adr/                # Architecture Decision Records
└── tests/                   # Root-level cross-component integration tests
```

## Component Architecture

All components follow a ports-and-adapters (hexagonal) pattern. Core business logic is interface-agnostic and lives in a service layer. Two adapters expose it:

- **Lambda handlers** (primary interface) — invoked by Step Functions, Lambda Function URLs, or API Gateway in production. Each component's `handler.py` is the production entry point.
- **CLI modules** (dev/testing only) — Typer-based command-line interfaces for local development and debugging. CLI modules are not bundled in Lambda deployments.

This separation means core logic can be tested independently of AWS infrastructure, and new adapters (e.g., HTTP servers, message queue consumers) can be added without modifying business logic.

## Prerequisites

- **Python 3.14+**
- **uv** package manager

## Quick Start

### Managed Pipeline (Primary)

Once the Phaeton pipeline is [deployed to AWS](docs/deployment.md), submit a workflow via the Step Functions state machine:

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT_ID:stateMachine:phaeton-conversion-pipeline \
  --input '{"workflow_name": "my-workflow", "workflow": { <n8n workflow JSON> }}'
```

When the execution completes, download the output zip from S3:

```bash
aws s3 cp s3://{output-bucket}/packages/my-workflow.zip .
unzip my-workflow.zip -d my-workflow
cd my-workflow/cdk && uv sync && uv run cdk deploy
```

See [Getting Started](docs/getting-started.md) for a full walkthrough including SSM credential setup.

### Local Development

Each component is an independent Python package with a dev-only CLI adapter for local testing. Run them from their respective directories:

```bash
# 1. Build a node catalog
cd n8n-release-parser && uv sync
uv run n8n-release-parser fetch-releases --months 6

# 2. Analyze a workflow
cd ../workflow-analyzer && uv sync
uv run workflow-analyzer path/to/workflow.json -o analysis/

# 3. Translate to ASL
cd ../n8n-to-sfn && uv sync
uv run n8n-to-sfn translate --input analysis.json -o output/

# 4. Package into a CDK app
cd ../packager && uv sync
uv run python -m n8n_to_sfn_packager --input translation_output.json -o output/
```

## Components

### n8n Release Parser

Maintains a versioned catalog of n8n node types with API specification matching. Fetches `n8n-nodes-base` releases from npm, diffs releases, and matches nodes against ~290 OpenAPI/Swagger specs.

- **Lambda handler:** `n8n_release_parser.handler`
- **Dev CLI:** `uv run n8n-release-parser <command>`
- [Component README](n8n-release-parser/README.md)

### Workflow Analyzer

Analyzes n8n workflow JSON exports — classifies nodes, builds dependency graphs, analyzes expressions, and generates conversion feasibility reports.

- **Lambda handler:** `workflow_analyzer.handler`
- **Dev CLI:** `uv run workflow-analyzer <workflow.json> -o <output/>`
- [Component README](workflow-analyzer/README.md)

### Translation Engine (n8n-to-sfn)

Converts analyzed workflows into ASL state machine definitions and supporting Lambda artifacts. Uses a plugin-based translator architecture with AI-powered translators for complex cases.

- **Lambda handler:** `n8n_to_sfn.handler`
- **Dev CLI:** `uv run n8n-to-sfn translate --input <input.json> -o <output/>`
- [Component README](n8n-to-sfn/README.md)

### Packager

Generates complete, deployable CDK applications from translation output. Produces ASL definitions, Lambda functions, IAM policies, SSM parameter placeholders, and a MIGRATE.md checklist.

- **Lambda handler:** `n8n_to_sfn_packager.handler`
- **Dev CLI:** `uv run python -m n8n_to_sfn_packager --input <input.json> -o <output/>`
- [Component README](packager/README.md)

### Node Translator

AI-powered translator that converts individual n8n workflow nodes into AWS Step Functions ASL states. Uses Strands Agents SDK with Claude Sonnet 4 via Amazon Bedrock.

- **Lambda handler:** `node_translator.handler`
- **Dev CLI:** `uv run node-translator <command>`
- [Component README](node-translator/README.md)

### Expression Translator

AI-powered translator that converts n8n expressions into JSONata expressions for use in AWS Step Functions. Uses Strands Agents SDK with Claude Sonnet 4 via Amazon Bedrock.

- **Lambda handler:** `expression_translator.handler`
- **Dev CLI:** `uv run expression-translator <command>`
- [Component README](expression-translator/README.md)

### Spec Registry

Standalone indexed registry of API specifications with S3-backed storage and event-driven index rebuilds. Provides API spec lookup for the release parser and translation engine.

- **Lambda handler:** `spec_registry.handler`
- **Dev CLI:** `uv run spec-registry <command>`
- [Component README](spec-registry/README.md)

### Shared Models (phaeton-models)

Shared Pydantic models and cross-component adapters used by all pipeline stages. Provides the common data contracts (`WorkflowAnalysis`, `TranslationOutput`, `PackagerInput`, etc.) that flow between components.

- **Library** (no CLI or Lambda handler)
- [Component README](shared/phaeton-models/README.md)

### Deployment

CDK application that deploys the Phaeton pipeline as AWS infrastructure. Creates CDK stacks including Lambda functions for each component, S3 buckets, a Step Functions orchestration state machine, and EventBridge scheduling.

- **CLI:** `uv run cdk deploy`
- [Deployment Guide](docs/deployment.md)

## Documentation

- [Getting Started](docs/getting-started.md) — installation, quickstart, and first workflow conversion
- [Architecture](docs/architecture.md) — system architecture, component details, operational concerns
- [Workflow Guide](docs/workflow-guide.md) — end-to-end data flow from workflow JSON to deployable zip
- [Supported Node Types](docs/supported-node-types.md) — reference of all translatable n8n nodes
- [Deployment Guide](docs/deployment.md) — deploying the Phaeton pipeline to AWS
- [Troubleshooting](docs/troubleshooting.md) — common errors and debugging tips
- [Architecture Decision Records](docs/adr/README.md) — key design decisions and their rationale

## Development

All components use the same toolchain. Run these commands from within each component directory:

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Lint and format
uv run ruff check --fix .
uv run ruff format .

# Type check
uv run ty check

# Test coverage
uv run coverage run -m pytest
uv run coverage report -m
```

## Technology Stack

| Technology | Role |
|---|---|
| Python 3.14 | Primary language |
| uv | Package management |
| Pydantic v2 | Data models and validation |
| Typer | Dev/testing CLI adapters |
| httpx | Async HTTP client |
| rapidfuzz | Fuzzy string matching (release parser) |
| aws-cdk-lib | CDK infrastructure definitions (packager) |
| jsonschema | ASL schema validation |
| ruff | Linting and formatting |
| pytest | Testing |
| coverage | Test coverage reporting |
| Strands Agents | AI agent framework (Bedrock integration) |
| ty | Type checking |
