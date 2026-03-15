# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Phaeton project. ADRs capture the context, decision, and consequences of significant architectural choices.

## Index

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [ADR-001](001-microservice-architecture.md) | Microservice Architecture | Accepted | Split the pipeline into 4 independent components with shared boundary models |
| [ADR-002](002-pydantic-v2-models.md) | Pydantic v2 for All Data Models | Accepted | Use Pydantic v2 BaseModel for all inter-component contracts and internal models |
| [ADR-003](003-jsonata-query-language.md) | JSONata as the Step Functions Query Language | Accepted | Generate all ASL state machines using JSONata instead of JSONPath |
| [ADR-004](004-strands-agents-ai-service.md) | AWS Strands Agents for AI Agent Service | Accepted | Use Strands Agents framework with Bedrock for the AI fallback translator |
| [ADR-005](005-lambda-function-urls.md) | Lambda Function URLs for Webhooks | Accepted | Use Lambda Function URLs instead of API Gateway for webhook endpoints |
| [ADR-006](006-rds-data-api.md) | RDS Data API for Database Support | Accepted | Translate database nodes to RDS Data API calls instead of VPC-bound drivers |
| [ADR-007](007-uv-package-manager.md) | uv as the Python Package Manager and Build Tool | Accepted | Use uv for dependency management, workspace orchestration, and builds |

## ADR Template

New ADRs should follow the template in each existing file:

```markdown
# ADR-NNN: <Title>

**Status:** Accepted | Proposed | Superseded
**Date:** YYYY-MM-DD

## Context
<What is the issue that we're seeing that motivates this decision?>

## Decision
<What is the change that we're proposing and/or doing?>

## Consequences
### Positive
- <benefit 1>
### Negative
- <tradeoff 1>
### Neutral
- <observation 1>
```
