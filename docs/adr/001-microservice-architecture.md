# ADR-001: Microservice Architecture

**Status:** Accepted
**Date:** 2025-06-01

## Context

Converting n8n workflows to AWS Step Functions is a multi-stage process with distinct concerns: cataloging n8n node types, analyzing workflow feasibility, translating nodes to ASL states, and packaging the result into a deployable CDK application. A monolithic design would couple these stages together, making it difficult to test, evolve, or replace any single stage independently.

## Decision

Split the pipeline into four independent components, each implemented as a standalone Python package:

1. **n8n Release Parser** (`n8n-release-parser/`) — maintains a versioned catalog of n8n node types with API specification matching.
2. **Workflow Analyzer** (`workflow-analyzer/`) — analyzes n8n workflow JSON exports and produces conversion feasibility reports.
3. **Translation Engine** (`n8n-to-sfn/`) — converts analyzed workflows into AWS Step Functions ASL and supporting Lambda artifacts.
4. **Packager** (`packager/`) — generates deployable CDK applications from translation output.

A fifth component, the **AI Agent** (`ai-agent/`), provides an optional fallback for nodes that deterministic translators cannot handle.

All inter-component data contracts are defined in a shared leaf package (`shared/phaeton-models/`), with adapter functions bridging boundary model differences between stages.

## Consequences

### Positive
- Each component can be developed, tested, and deployed independently.
- Component boundaries are enforced by Pydantic models, catching contract violations at validation time rather than at runtime deep in the pipeline.
- Individual stages can be replaced or upgraded without affecting the rest of the pipeline (e.g., swapping the AI agent backend).
- Components can scale independently when deployed as services.

### Negative
- Inter-component contracts require explicit adapter code to bridge model differences between stages.
- Changes that span multiple components require coordinated updates across packages.
- The shared `phaeton-models` package must remain a strict leaf dependency with no imports from service packages, which constrains where shared logic can live.

### Neutral
- The data flow is strictly linear: Release Parser → Workflow Analyzer → Translation Engine → Packager. There are no circular dependencies between components.
- Each component has its own `pyproject.toml`, test suite, and `uv.lock`, enabling fully independent CI runs.
