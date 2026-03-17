# Phaeton

Converts n8n workflows into deployable AWS Step Functions CDK applications.

## Overview

Phaeton is a managed pipeline that converts n8n workflow JSON exports into complete, deployable AWS CDK applications. Submit a workflow JSON, and Phaeton produces a zip archive containing an ASL state machine definition, Lambda functions, IAM policies, SSM credential placeholders, CDK infrastructure code, and a migration guide — ready to extract and deploy with `cdk deploy`.

The pipeline is deployed as AWS infrastructure (6 CDK stacks) with a Step Functions state machine (`phaeton-conversion-pipeline`) orchestrating the end-to-end conversion. It uses deterministic translation wherever possible and an AI agent (Bedrock + Claude Sonnet 4) as a fallback for complex cases.

## Architecture

Phaeton is built as 4 independent microservices, each with its own Lambda, codebase, and test suite. Services communicate only via well-defined contracts defined in phaeton-models. A Step Functions state machine orchestrates them sequentially:

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
│  Deterministic ASL translation + AI fallback     │
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
├── n8n-release-parser/      # Component 1: node catalog & API spec matching
├── workflow-analyzer/       # Component 2: workflow analysis & feasibility reports
├── n8n-to-sfn/              # Component 3: translation engine
├── packager/                # Component 4: CDK application generator
├── shared/phaeton-models/   # Shared Pydantic models and cross-component adapters
├── deployment/              # CDK deployment stacks for the Phaeton pipeline
├── ai-agent/                # AI agent fallback for complex node translation
├── docs/                    # Architecture plans & coding guidelines
│   └── adr/                # Architecture Decision Records
└── tests/                   # Root-level cross-component integration tests
```

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

Each component is an independent Python package. For development and testing, run them locally from their respective directories:

```bash
# 1. Build a node catalog
cd n8n-release-parser && uv sync
uv run n8n-release-parser fetch-releases --months 6

# 2. Analyze a workflow
cd ../workflow-analyzer && uv sync
uv run workflow-analyzer path/to/workflow.json -o analysis/

# 3. Translate (library — called by the Packager or programmatically)
cd ../n8n-to-sfn && uv sync

# 4. Package into a CDK app
cd ../packager && uv sync
uv run python -m n8n_to_sfn_packager --input translation_output.json -o output/
```

## Components

### n8n Release Parser

Maintains a versioned catalog of n8n node types with API specification matching. Fetches `n8n-nodes-base` releases from npm, diffs releases, and matches nodes against ~290 OpenAPI/Swagger specs.

- **CLI:** `uv run n8n-release-parser <command>`
- [Component README](n8n-release-parser/README.md)

### Workflow Analyzer

Analyzes n8n workflow JSON exports — classifies nodes, builds dependency graphs, analyzes expressions, and generates conversion feasibility reports.

- **CLI:** `uv run workflow-analyzer <workflow.json> -o <output/>`
- [Component README](workflow-analyzer/README.md)

### Translation Engine (n8n-to-sfn)

Converts analyzed workflows into ASL state machine definitions and supporting Lambda artifacts. Uses a plugin-based translator architecture with an AI agent fallback for complex cases.

- **Library** (no CLI) — used by the Packager or invoked programmatically
- [Component README](n8n-to-sfn/README.md)

### Packager

Generates complete, deployable CDK applications from translation output. Produces ASL definitions, Lambda functions, IAM policies, SSM parameter placeholders, and a MIGRATE.md checklist.

- **CLI:** `uv run python -m n8n_to_sfn_packager --input <input.json> -o <output/>`
- [Component README](packager/README.md)

### Shared Models (phaeton-models)

Shared Pydantic models and cross-component adapters used by all pipeline stages. Provides the common data contracts (`WorkflowAnalysis`, `TranslationOutput`, `PackagerInput`, etc.) that flow between components.

- **Library** (no CLI)
- [Component README](shared/phaeton-models/README.md)

### Deployment

CDK application that deploys the Phaeton pipeline as AWS infrastructure. Creates 6 CDK stacks including Lambda functions for each component, S3 buckets, a Step Functions orchestration state machine, and EventBridge scheduling.

- **CLI:** `uv run cdk deploy`
- [Deployment Guide](docs/deployment.md)

### AI Agent

Bedrock-powered fallback translation service for n8n nodes and expressions that cannot be translated deterministically. Uses Strands Agents SDK with Claude Sonnet 4 via Amazon Bedrock.

- **Library** (invoked as Lambda by the Translation Engine)
- [AI Agent Guide](docs/ai-agent.md)

## Documentation

- [Getting Started](docs/getting-started.md) — installation, quickstart, and first workflow conversion
- [Architecture](docs/architecture.md) — system architecture, component details, operational concerns
- [Workflow Guide](docs/workflow-guide.md) — end-to-end data flow from workflow JSON to deployable zip
- [Supported Node Types](docs/supported-node-types.md) — reference of all translatable n8n nodes
- [Deployment Guide](docs/deployment.md) — deploying the Phaeton pipeline to AWS
- [AI Agent Guide](docs/ai-agent.md) — AI-powered fallback translation service
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
| Typer | CLI interfaces |
| httpx | Async HTTP client |
| rapidfuzz | Fuzzy string matching (release parser) |
| aws-cdk-lib | CDK infrastructure definitions (packager) |
| jsonschema | ASL schema validation |
| ruff | Linting and formatting |
| pytest | Testing |
| coverage | Test coverage reporting |
| Strands Agents | AI agent framework (Bedrock integration) |
| ty | Type checking |
