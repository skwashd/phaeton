# Update Architecture And Agent Documentation

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #22

## Overview

`docs/architecture.md` needs to show the split agents, spec-registry component, and ports-and-adapters pattern. `docs/ai-agent.md` needs to be replaced with documentation for both new AI translator components (node-translator and expression-translator).

## Dependencies

- **Blocked by:** TASK-0009 (ai-agent deleted), TASK-0006 (spec-registry exists), TASK-0010 (release-parser refactored), TASK-0011 (analyzer refactored), TASK-0012 (packager refactored), TASK-0013 (n8n-to-sfn CLI)
- **Blocks:** None

## Acceptance Criteria

1. `docs/architecture.md` shows the updated component diagram with split agents and spec-registry.
2. `docs/architecture.md` documents the ports-and-adapters pattern.
3. `docs/ai-agent.md` is replaced with documentation covering both node-translator and expression-translator.
4. No stale references to the monolithic ai-agent component.

## Implementation Details

### Files to Modify

- `docs/architecture.md`
- `docs/ai-agent.md`

### Technical Approach

1. **Update `architecture.md`:**
   - Update component diagram to show node-translator and expression-translator as separate services.
   - Add spec-registry as a component.
   - Document the ports-and-adapters pattern: core logic, Lambda adapter, CLI adapter.
   - Update data flow diagrams to show two Lambda invocations from the translation engine.

2. **Replace `docs/ai-agent.md`:**
   - Rename or rewrite to cover both translator components.
   - Document each component's purpose, request/response contracts, and deployment model.
   - Document the system prompts and how they differ between node and expression translation.

### Testing Requirements

- Visual review for accuracy.
- Verify all referenced component names and paths exist.
