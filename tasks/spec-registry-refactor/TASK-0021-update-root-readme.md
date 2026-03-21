# Update Root Readme

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #21

## Overview

The root `README.md` needs to reflect the new component structure, remove CLI-as-primary-interface language, and document that all components expose Lambda handlers for Step Functions, Lambda Function URLs, and API Gateway. The ports-and-adapters pattern should be documented.

## Dependencies

- **Blocked by:** TASK-0009 (ai-agent deleted), TASK-0010 (release-parser refactored), TASK-0011 (analyzer refactored), TASK-0012 (packager refactored), TASK-0013 (n8n-to-sfn CLI added)
- **Blocks:** None

## Acceptance Criteria

1. Component list shows node-translator, expression-translator, spec-registry (not ai-agent).
2. Primary interface is documented as Lambda handlers.
3. CLI is described as dev/testing only.
4. Ports-and-adapters pattern is explained.
5. No stale references to old component names or structures.

## Implementation Details

### Files to Modify

- `README.md`

### Technical Approach

1. Update component descriptions in the overview section.
2. Add a "Component Architecture" section explaining ports-and-adapters: core logic is interface-agnostic, Lambda handlers and CLI are adapters.
3. Remove or rewrite any language that presents CLIs as the primary way to use components.

### Testing Requirements

- Visual review for accuracy and completeness.
