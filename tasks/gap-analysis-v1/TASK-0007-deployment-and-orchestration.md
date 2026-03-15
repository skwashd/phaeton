# Deployment And Orchestration

**Priority:** P0
**Effort:** M
**Gap Analysis Ref:** Item #7

## Overview

Phaeton is a system of independent microservices with no deployment infrastructure or service orchestration. Three capabilities are missing:

1. **Deployment infrastructure** — No IaC (CDK/CloudFormation) to deploy all components as services. Each component needs its own deployment stack with appropriate compute (Lambda, ECS, etc.).
2. **Release Parser trigger** — No mechanism to trigger the n8n Release Parser for an initial import of node metadata, then automatically after each new n8n release (e.g., via EventBridge scheduled rule or webhook).
3. **Workflow conversion flow** — When a user submits a workflow for conversion, it must pass through three stages in sequence: Workflow Analyzer -> Translation Engine -> Packager. No event-driven orchestration exists to move a workflow through these stages (e.g., via SQS queues, Step Functions, or direct service invocation).

## Dependencies

- **Blocked by:** TASK-0001, TASK-0002, TASK-0004, TASK-0005, TASK-0006
- **Blocks:** TASK-0016, TASK-0031

## Acceptance Criteria

1. A CDK application exists that defines deployment stacks for each Phaeton component.
2. Each component has a compute target (Lambda function or ECS task) with appropriate IAM roles, environment variables, and resource limits.
3. An EventBridge rule or similar mechanism triggers the Release Parser on a schedule (e.g., daily) and/or on demand.
4. A workflow conversion orchestration exists (e.g., a Step Functions state machine or API Gateway + Lambda pipeline) that:
   - Accepts an n8n workflow JSON as input.
   - Invokes the Workflow Analyzer.
   - Passes the result through the adapter (TASK-0001) to the Translation Engine.
   - Passes the translation output through the adapter (TASK-0002) to the Packager.
   - Returns or stores the generated CDK application package.
5. Each component's service entry point (Lambda handler or API endpoint) is defined and deployable.
6. `uv run ruff check` passes on any new Python code.

## Implementation Details

Always use ARM64 as the compute architecture

### Files to Modify

- `deployment/` (new directory)
- `deployment/app.py` (CDK app entry point)
- `deployment/stacks/` (stack definitions)
- `deployment/stacks/release_parser_stack.py`
- `deployment/stacks/workflow_analyzer_stack.py`
- `deployment/stacks/translation_engine_stack.py`
- `deployment/stacks/packager_stack.py`
- `deployment/stacks/orchestration_stack.py`

### Technical Approach

1. **CDK Application Structure:**
   - Create a `deployment/` directory with a CDK app.
   - Each component gets its own stack for independent deployment and scaling.
   - An orchestration stack ties the components together.

2. **Release Parser Stack:**
   - Lambda function packaging the `n8n-release-parser` code.
   - EventBridge rule triggering daily or on-demand.
   - S3 bucket or DynamoDB table to store parsed node metadata.

3. **Workflow Analyzer Stack:**
   - Lambda function (or ECS task for larger workflows) packaging the `workflow-analyzer` code.
   - API Gateway or Lambda Function URL for invocation.

4. **Translation Engine Stack:**
   - Lambda function packaging the `n8n-to-sfn` code.
   - Requires TASK-0015 (service entry point) to be complete.

5. **Packager Stack:**
   - Lambda function packaging the `packager` code.
   - S3 bucket for storing generated CDK application packages.

6. **Orchestration Stack:**
   - Step Functions state machine that chains: Analyzer -> Adapter 1 -> Translator -> Adapter 2 -> Packager.
   - Or: API Gateway -> Lambda orchestrator that calls each service sequentially.
   - Error handling and retry logic at each stage.

### Testing Requirements

- CDK synth test: `cdk synth` produces valid CloudFormation templates.
- Unit tests for each stack definition.
- Smoke test: deploy to a test account and run a simple workflow through the pipeline (deferred to TASK-0016).
