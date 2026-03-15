# Architecture Decision Records

**Priority:** Documentation
**Effort:** M
**Gap Analysis Ref:** Docs table row 4

## Overview

No architecture decision records (ADRs) exist documenting the key design decisions made in Phaeton's development. ADRs capture the context, decision, and consequences of significant architectural choices, making it easier for new contributors to understand why the system is designed the way it is and preventing re-litigation of settled decisions.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A `docs/adr/` directory exists with numbered ADR files.
2. At minimum, ADRs exist for the following decisions:
   - ADR-001: Microservice architecture (4 independent components).
   - ADR-002: Pydantic v2 for all data models.
   - ADR-003: JSONata as the Step Functions query language (not JSONPath).
   - ADR-004: AWS Strands Agents for the AI agent service (not custom LLM integration).
   - ADR-005: Lambda Function URLs for webhooks (not API Gateway).
   - ADR-006: RDS Data API for database support (not VPC-bound drivers).
   - ADR-007: `uv` as the Python package manager and build tool.
3. Each ADR follows a consistent template (title, status, context, decision, consequences).
4. ADRs are linked from the top-level documentation.

## Implementation Details

### Files to Modify

- `docs/adr/` (new directory)
- `docs/adr/README.md` (index of all ADRs)
- `docs/adr/001-microservice-architecture.md`
- `docs/adr/002-pydantic-v2-models.md`
- `docs/adr/003-jsonata-query-language.md`
- `docs/adr/004-strands-agents-ai-service.md`
- `docs/adr/005-lambda-function-urls.md`
- `docs/adr/006-rds-data-api.md`
- `docs/adr/007-uv-package-manager.md`

### Technical Approach

1. **ADR template:**
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

2. **Key decisions to document:**

   **ADR-001: Microservice Architecture**
   - Context: n8n workflow conversion is a multi-stage process with distinct concerns.
   - Decision: Split into 4 independent components (Release Parser, Workflow Analyzer, Translation Engine, Packager).
   - Consequences: Independent deployment and scaling, but requires inter-component contracts and adapters.

   **ADR-003: JSONata Query Language**
   - Context: Step Functions supports two query languages: JSONPath (legacy) and JSONata (modern).
   - Decision: All generated state machines use JSONata exclusively.
   - Consequences: Modern syntax, more expressive, but narrower community documentation.

   **ADR-005: Lambda Function URLs**
   - Context: Webhooks need public HTTP endpoints.
   - Decision: Use Lambda Function URLs instead of API Gateway.
   - Consequences: Simpler setup, lower cost, but random AWS-assigned domains (custom domain deferred to TASK-0029).

3. **Index file** (`docs/adr/README.md`):
   - Lists all ADRs with their status and a one-line summary.
   - Links to each ADR file.

### Testing Requirements

- Verify all ADR files follow the template structure.
- Verify the index file lists all ADR files.
- Verify all cross-references between ADRs and task files are valid.
