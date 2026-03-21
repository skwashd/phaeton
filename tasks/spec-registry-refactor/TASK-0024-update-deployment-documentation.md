# Update Deployment Documentation

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #24

## Overview

`docs/deployment.md` needs to reflect the new stack structure: two AI translator Lambdas instead of one, the spec-registry stack with S3 bucket and event-driven Lambda, and the updated TranslationEngineStack wiring.

## Dependencies

- **Blocked by:** TASK-0017 (app.py finalized), TASK-0018 (deployment tests updated)
- **Blocks:** None

## Acceptance Criteria

1. `docs/deployment.md` documents all current stacks: NodeTranslatorStack, ExpressionTranslatorStack, SpecRegistryStack, TranslationEngineStack, ReleaseParserStack, WorkflowAnalyzerStack, PackagerStack.
2. AiAgentStack is not referenced.
3. Stack dependencies and wiring are documented.
4. Lambda function names and environment variables are listed.
5. Spec-registry S3 event trigger is documented.

## Implementation Details

### Files to Modify

- `docs/deployment.md`

### Technical Approach

1. Read the current `docs/deployment.md` to understand the existing structure.

2. Replace the AiAgentStack section with separate sections for NodeTranslatorStack and ExpressionTranslatorStack.

3. Add a SpecRegistryStack section documenting: S3 bucket, Lambda indexer, event trigger.

4. Update the TranslationEngineStack section to show two function dependencies.

5. Update any architecture diagrams or tables.

### Testing Requirements

- Visual review for accuracy.
- Verify all Lambda function names and env vars match the CDK code.
