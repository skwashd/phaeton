# Phaeton

Converts n8n workflows into deployable AWS Step Functions CDK applications.

## Overview

Phaeton is a modular platform for enterprise migration from n8n to AWS-native orchestration. It takes an n8n workflow JSON export as input and produces a complete, deployable CDK application containing the equivalent AWS Step Functions state machine, Lambda functions, IAM policies, SSM credential placeholders, and a migration guide.

The system uses deterministic translation wherever possible (flow control, AWS service nodes, expressions) and an AI agent as a fallback for complex cases that can't be mapped mechanically.

## Architecture

Phaeton is a 4-component pipeline. Each component can be used independently but they are designed to flow sequentially:

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
                       │  WorkflowAnalysis
                       ▼
┌──────────────────────────────────────────────────┐
│  3. Translation Engine (n8n-to-sfn)              │
│  Deterministic ASL translation + AI fallback     │
│  Lambda artifacts, trigger configs, variables    │
└──────────────────────┬───────────────────────────┘
                       │  TranslationOutput → PackagerInput JSON
                       ▼
┌──────────────────────────────────────────────────┐
│  4. Packager                                     │
│  CDK app, ASL definition, Lambda code, IAM,      │
│  SSM params, MIGRATE.md, conversion reports      │
└──────────────────────────────────────────────────┘
        │
        ▼
  Deployable CDK Application
```

## Project Structure

```
phaeton/end-to-end/
├── n8n-release-parser/   # Component 1: node catalog & API spec matching
├── workflow-analyzer/    # Component 2: workflow analysis & feasibility reports
├── n8n-to-sfn/           # Component 3: translation engine
├── packager/             # Component 4: CDK application generator
└── docs/                 # Architecture plans & coding guidelines
```

## Prerequisites

- **Python 3.14** (3.13 for workflow-analyzer)
- **uv** package manager

## Quick Start

Each component is an independent Python package. Install and use them from their respective directories:

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
| Python 3.14 | Primary language (3.13 for workflow-analyzer) |
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
| ty | Type checking |
