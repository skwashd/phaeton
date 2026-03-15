# Troubleshooting Guide

**Priority:** Documentation
**Effort:** S
**Gap Analysis Ref:** Docs table row 3

## Overview

No troubleshooting guide exists for common issues users encounter when converting workflows or deploying generated CDK applications. A troubleshooting guide reduces support burden and helps users self-serve when they encounter errors.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A `docs/troubleshooting.md` file exists with categorized solutions to common problems.
2. The guide covers issues in each pipeline stage: analysis, translation, packaging, deployment.
3. Each issue includes: symptoms, root cause, and resolution steps.
4. The guide includes common error messages with explanations.
5. The guide cross-references relevant TASK files for known limitations.

## Implementation Details

### Files to Modify

- `docs/troubleshooting.md` (new)

### Technical Approach

1. **Document structure:**
   - **Analysis Issues:** Problems with workflow JSON parsing, unsupported node types.
   - **Translation Issues:** Failed translations, placeholder warnings, ASL validation errors.
   - **Packaging Issues:** CDK code generation errors, missing dependencies.
   - **Deployment Issues:** `cdk deploy` failures, IAM permission errors, Lambda runtime errors.
   - **Runtime Issues:** State machine execution failures, timeout errors, data format mismatches.

2. **Example entries:**

   **Issue: "Unsupported node type" warning**
   - Symptoms: Translation warning mentioning unsupported node type.
   - Cause: The node type is not in any translator's dispatch table.
   - Resolution: Check `docs/supported-node-types.md` for supported types. Use the AI agent fallback (TASK-0008) for automatic translation, or manually implement the state.

   **Issue: "CDK synth fails with ImportError"**
   - Symptoms: `cdk synth` fails with Python import errors.
   - Cause: Missing CDK dependencies in the generated project.
   - Resolution: Run `pip install -r requirements.txt` in the generated CDK project directory.

   **Issue: "State machine execution fails with Access Denied"**
   - Symptoms: Step Functions execution fails with IAM permission error.
   - Cause: Generated IAM policy does not include required permissions for the target service.
   - Resolution: Check the execution error for the specific action/resource denied. Add the permission to the generated IAM policy. See TASK-0009 for wildcard ARN improvements.

3. **Error message reference:**
   - Include a searchable table of common error messages and their meanings.
   - Link to the relevant troubleshooting section for each error.

### Testing Requirements

- All code snippets and CLI commands in the guide should be valid.
- Cross-reference with existing test fixtures for example error scenarios.
