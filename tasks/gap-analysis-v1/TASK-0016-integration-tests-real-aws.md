# Integration Tests Real Aws

**Priority:** P1
**Effort:** L
**Gap Analysis Ref:** Item #16

## Overview

All tests are unit tests using mocks and fixtures. No test deploys a generated CDK stack to AWS, executes the resulting state machine, or validates the output. Without integration tests, there is no confidence that generated ASL is accepted by Step Functions, that IAM policies grant sufficient (but not excessive) permissions, or that Lambda functions execute correctly.

## Dependencies

- **Blocked by:** TASK-0007 (deployment infrastructure must exist first)
- **Blocks:** None

## Acceptance Criteria

1. An integration test suite exists that can deploy a generated CDK stack to a real AWS account.
2. At least one test workflow (simple DynamoDB + Lambda) is deployed end-to-end.
3. The deployed state machine executes successfully with test input data.
4. The test validates that the state machine output matches expected results.
5. IAM policies are verified to be sufficient (execution succeeds) and not excessively broad.
6. Lambda functions execute without runtime errors.
7. Tests clean up all deployed resources after execution (stack deletion).
8. Integration tests are marked with a pytest marker (e.g., `@pytest.mark.integration`) so they can be run separately from unit tests.
9. `uv run pytest -m integration` runs the integration tests (requires AWS credentials).

## Implementation Details

### Files to Modify

- `tests/integration/` (new directory at repo root)
- `tests/integration/conftest.py` (AWS fixtures, stack deployment helpers)
- `tests/integration/test_simple_workflow.py` (first integration test)
- `tests/integration/fixtures/` (test workflow JSON files)

### Technical Approach

1. **Test infrastructure:**
   - Use `pytest` with custom markers for integration tests.
   - Use `boto3` for CDK deployment (`cdk deploy` via subprocess) and AWS API calls.
   - Create fixtures that deploy a stack, yield the stack outputs, and tear down on cleanup.

2. **Test workflow:**
   - Create a simple n8n workflow JSON: Trigger -> DynamoDB Put -> DynamoDB Get -> Response.
   - Run the full pipeline: Analyzer -> Translator -> Packager -> CDK Deploy.
   - Execute the state machine via `sfn.start_execution()`.
   - Wait for completion and validate output.

3. **Resource cleanup:**
   - Use `pytest` fixture finalizers to run `cdk destroy` after each test.
   - Add a timeout to prevent hanging if cleanup fails.
   - Tag all resources with a `phaeton-test` tag for manual cleanup if needed.

4. **AWS credentials:**
   - Tests require valid AWS credentials (via environment variables or AWS profile).
   - Use a dedicated test account or sandbox.
   - Document required IAM permissions for the test runner.

### Testing Requirements

- Integration tests must be idempotent (can be re-run without manual cleanup).
- Tests must clean up all AWS resources (CloudFormation stacks, Lambda functions, state machines, DynamoDB tables).
- Tests should timeout after a reasonable period (e.g., 10 minutes per test).
- Test output should clearly report success/failure with relevant CloudWatch log references.
