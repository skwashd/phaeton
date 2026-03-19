# Update Component Claude Md Files

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #23

## Overview

New components (node-translator, expression-translator, spec-registry) need their own CLAUDE.md files. Existing component CLAUDE.md files need updates to reflect the ports-and-adapters pattern and dev-only CLI usage. The `n8n-release-parser/CLAUDE.md` needs spec references removed.

## Dependencies

- **Blocked by:** TASK-0004 (node-translator exists), TASK-0005 (expression-translator exists), TASK-0006 (spec-registry exists), TASK-0007 (release-parser cleaned), TASK-0010 (release-parser P&A), TASK-0011 (analyzer P&A), TASK-0012 (packager P&A), TASK-0013 (n8n-to-sfn CLI)
- **Blocks:** None

## Acceptance Criteria

1. `node-translator/CLAUDE.md` exists with accurate component description, commands, and conventions.
2. `expression-translator/CLAUDE.md` exists with accurate component description, commands, and conventions.
3. `spec-registry/CLAUDE.md` exists with accurate component description, commands, and conventions.
4. `n8n-release-parser/CLAUDE.md` has no spec-related references.
5. All existing component CLAUDE.md files mention that CLI is dev-only and handler is the primary interface.

## Implementation Details

### Files to Modify

- `node-translator/CLAUDE.md` (new)
- `expression-translator/CLAUDE.md` (new)
- `spec-registry/CLAUDE.md` (new)
- `n8n-release-parser/CLAUDE.md`
- `workflow-analyzer/CLAUDE.md`
- `packager/CLAUDE.md`
- `n8n-to-sfn/CLAUDE.md`

### Technical Approach

1. **Create new CLAUDE.md files** following the pattern of existing component CLAUDE.md files. Include: component purpose, commands (uv sync, pytest, ruff, ty), package structure, key modules, dev CLI usage.

2. **Update existing CLAUDE.md files** to add a note about ports-and-adapters: handler is the Lambda entry point, CLI is dev-only.

3. **Clean `n8n-release-parser/CLAUDE.md`** of any spec index or matcher references.

### Testing Requirements

- Visual review for accuracy and completeness.
