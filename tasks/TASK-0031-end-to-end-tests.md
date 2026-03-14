# End To End Tests

**Priority:** Testing
**Effort:** L
**Gap Analysis Ref:** Testing table row 1

## Overview

No end-to-end tests exist that take a real n8n workflow JSON file through the complete pipeline (Workflow Analyzer -> Translation Engine -> Packager) and verify the output is a valid, deployable CDK application. Without these tests, there is no confidence that the components work together correctly, that the adapter layers (TASK-0001, TASK-0002) produce compatible data, or that the final output is usable.

## Dependencies

- **Blocked by:** TASK-0001, TASK-0002, TASK-0007
- **Blocks:** None

## Acceptance Criteria

1. An end-to-end test suite exists at the repository root level (`tests/e2e/`).
2. At least 3 representative n8n workflow JSON files are used as test fixtures.
3. Each test runs the complete pipeline: Analyzer -> Adapter -> Translator -> Adapter -> Packager.
4. The generated CDK application output is validated:
   - CDK Python code is syntactically valid.
   - ASL JSON is valid according to the Step Functions JSON schema.
   - IAM policy document is valid.
   - SSM parameter definitions are present for all required credentials.
5. Tests verify that no data is lost or corrupted at inter-component boundaries.
6. Tests pass with `uv run pytest tests/e2e/`.

## Implementation Details

### Files to Modify

- `tests/e2e/` (new directory at repo root)
- `tests/e2e/conftest.py` (pipeline fixtures)
- `tests/e2e/test_simple_workflow.py` (simple DynamoDB workflow)
- `tests/e2e/test_lambda_workflow.py` (workflow with Code nodes)
- `tests/e2e/test_scheduled_workflow.py` (workflow with schedule trigger)
- `tests/e2e/fixtures/` (n8n workflow JSON files)

### Technical Approach

1. **Test fixtures:**
   - `simple_dynamodb.json`: Trigger -> DynamoDB PutItem -> DynamoDB GetItem.
   - `code_node.json`: Trigger -> Code (JS) -> SNS Publish.
   - `scheduled.json`: Schedule Trigger -> Lambda -> SQS SendMessage.

2. **Pipeline execution:**
   ```python
   def run_pipeline(workflow_json: dict) -> Path:
       # Step 1: Analyze
       report = WorkflowAnalyzer().analyze(workflow_json)
       # Step 2: Adapt (TASK-0001)
       analysis = convert_report_to_analysis(report)
       # Step 3: Translate
       engine = create_default_engine()
       output = engine.translate(analysis)
       # Step 4: Adapt (TASK-0002)
       packager_input = convert_output_to_packager_input(output, "test-workflow")
       # Step 5: Package
       output_dir = Packager().package(packager_input)
       return output_dir
   ```

3. **Output validation:**
   - Parse generated CDK Python code with `ast.parse()` to verify syntax.
   - Validate ASL JSON against the Step Functions JSON schema.
   - Verify IAM policy structure.
   - Check file counts and directory structure.

4. **Boundary validation:**
   - Assert no Pydantic `ValidationError` occurs at any adapter boundary.
   - Assert all classified nodes from the analyzer appear in the translation output.
   - Assert all Lambda artifacts from the translator appear in the packager output.

### Testing Requirements

- Each test workflow should exercise a different code path through the pipeline.
- Tests should be deterministic (no randomness, no external dependencies).
- Tests should complete in < 30 seconds each.
