# Update Root Claude Md

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #20

## Overview

The root `CLAUDE.md` contains a repo structure diagram that references `ai-agent/` and `src/phaeton_integration_tests/`. After the restructuring, the diagram should show `node-translator/`, `expression-translator/`, and `spec-registry/` instead of `ai-agent/`, and the empty `src/phaeton_integration_tests/` should be gone. Additionally, guidance should clarify that CLIs are dev/testing only and Lambda functions are the primary interface.

## Dependencies

- **Blocked by:** TASK-0009 (ai-agent deleted), TASK-0003 (integration tests dir deleted), TASK-0007 (release-parser cleaned)
- **Blocks:** None

## Acceptance Criteria

1. Repo structure diagram shows `node-translator/`, `expression-translator/`, `spec-registry/`.
2. `ai-agent/` is not in the diagram.
3. `src/phaeton_integration_tests/` is not referenced.
4. Guidance states CLIs are dev/testing only; Lambda handlers are the primary interface.
5. Component descriptions are accurate.

## Implementation Details

### Files to Modify

- `CLAUDE.md`

### Technical Approach

1. Update the repo structure tree to replace `ai-agent/` with:
   ```
   ├── node-translator/       # AI agent for n8n node → ASL state translation
   ├── expression-translator/  # AI agent for n8n expression → JSONata translation
   ├── spec-registry/          # API specification registry and indexer
   ```

2. Remove the `ai-agent/` line.

3. Add a section or note under "Code conventions" about ports-and-adapters:
   - Lambda handlers are the primary interface for all components.
   - CLI modules are dev/testing adapters only, not bundled in Lambda deployments.
   - Typer is a dev dependency in all components.

### Testing Requirements

- Visual review of the updated CLAUDE.md for accuracy.
