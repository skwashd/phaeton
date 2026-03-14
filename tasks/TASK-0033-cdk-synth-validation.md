# Cdk Synth Validation

**Priority:** Testing
**Effort:** S
**Gap Analysis Ref:** Testing table row 3

## Overview

No `cdk synth` validation exists for generated CDK applications. The packager generates Python CDK code, but there is no automated check that the generated code successfully synthesizes into valid CloudFormation templates. `cdk synth` failures would only be discovered when a user tries to deploy, which is too late for a good developer experience.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A test suite validates that generated CDK applications pass `cdk synth`.
2. At least 3 representative workflow scenarios are tested.
3. The test verifies that the synthesized CloudFormation template contains expected resources (state machine, Lambda functions, IAM roles, etc.).
4. Tests run in a CI-compatible environment (no AWS credentials required for synth).
5. Failures in generated CDK code are reported with clear error messages.
6. `uv run pytest` passes for the CDK synth tests.

## Implementation Details

### Files to Modify

- `tests/cdk_synth/` (new directory at repo root)
- `tests/cdk_synth/conftest.py` (CDK app fixtures)
- `tests/cdk_synth/test_synth_simple.py`
- `tests/cdk_synth/test_synth_lambda.py`
- `tests/cdk_synth/test_synth_scheduled.py`

### Technical Approach

1. **CDK synth via subprocess:**
   ```python
   def synth_cdk_app(app_dir: Path) -> dict:
       result = subprocess.run(
           ["cdk", "synth", "--json"],
           cwd=app_dir,
           capture_output=True, text=True,
       )
       assert result.returncode == 0, f"cdk synth failed: {result.stderr}"
       return json.loads(result.stdout)
   ```

2. **CDK synth via Python CDK API:**
   ```python
   from aws_cdk import App
   app = App()
   # Import the generated stack
   template = Template.from_stack(stack)
   template.has_resource_properties("AWS::StepFunctions::StateMachine", {...})
   ```

3. **Test scenarios:**
   - Simple workflow: Trigger -> DynamoDB -> Response.
   - Lambda workflow: Trigger -> Code node -> SNS.
   - Scheduled workflow: EventBridge Schedule -> Lambda -> SQS.

4. **Template assertions:**
   - Verify `AWS::StepFunctions::StateMachine` resource exists with correct definition.
   - Verify `AWS::Lambda::Function` resources exist for each Lambda artifact.
   - Verify `AWS::IAM::Role` resources with expected policies.
   - Verify `AWS::Events::Rule` resources for scheduled triggers.
   - Verify `AWS::SSM::Parameter` resources for credentials.

### Testing Requirements

- Tests must not require AWS credentials (use `cdk synth` which runs locally).
- Tests should run in < 60 seconds.
- CDK and Node.js must be available in the test environment.
