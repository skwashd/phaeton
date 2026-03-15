# Getting Started Guide

**Priority:** Documentation
**Effort:** S
**Gap Analysis Ref:** Docs table row 1

## Overview

No user-facing getting-started guide exists. New users have no clear path to understand what Phaeton does, how to install it, or how to convert their first n8n workflow. A getting-started guide is essential for adoption and reduces the support burden.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A `docs/getting-started.md` file exists with clear, step-by-step instructions.
2. The guide covers: prerequisites, installation, first workflow conversion, deploying the output.
3. Prerequisites list all required tools (Python 3.14+, `uv`, Node.js, AWS CDK, AWS CLI).
4. Installation instructions cover all 4 components.
5. A complete example walks through converting a simple n8n workflow JSON to a deployed Step Function.
6. The guide includes troubleshooting tips for common setup issues.
7. All code snippets in the guide are tested and work.

## Implementation Details

### Files to Modify

- `docs/getting-started.md` (new)

### Technical Approach

1. **Document structure:**
   - **Prerequisites:** Python 3.14+, `uv`, Node.js 20+, AWS CDK CLI, AWS CLI with configured credentials.
   - **Installation:** Clone the repo, install each component with `uv sync`.
   - **Quick Start:** Convert a sample workflow end-to-end.
   - **Understanding the Output:** Explain the generated CDK application structure.
   - **Deploying:** Run `cdk deploy` to deploy the converted workflow.
   - **Troubleshooting:** Common errors and solutions.

2. **Sample workflow:**
   - Include a simple n8n workflow JSON (e.g., Schedule Trigger -> DynamoDB PutItem) as an inline example.
   - Walk through each pipeline stage with expected input/output.

3. **Code examples:**
   ```bash
   # Install all components
   cd workflow-analyzer && uv sync
   cd ../n8n-to-sfn && uv sync
   cd ../packager && uv sync
   cd ../n8n-release-parser && uv sync

   # Convert a workflow
   python -m phaeton.convert my-workflow.json --output ./output/
   ```

4. **Verification steps:**
   - Verify the generated CDK app with `cdk synth`.
   - Deploy with `cdk deploy`.
   - Test the deployed state machine.

### Testing Requirements

- All code snippets should be copy-pastable and functional.
- The sample workflow JSON should be valid and included in the repository.
- Cross-reference with TASK-0018 for credential setup instructions.
