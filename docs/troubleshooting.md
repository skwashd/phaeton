# Troubleshooting Guide

This guide covers common issues encountered when converting n8n workflows to AWS Step Functions using the Phaeton pipeline. Issues are organized by pipeline stage: analysis, translation, packaging, deployment, and runtime.

## Table of Contents

- [Analysis Issues](#analysis-issues)
- [Translation Issues](#translation-issues)
- [Packaging Issues](#packaging-issues)
- [Deployment Issues](#deployment-issues)
- [Runtime Issues](#runtime-issues)
- [Error Message Reference](#error-message-reference)

---

## Analysis Issues

### Workflow JSON fails to parse

**Symptoms:** The workflow analyzer returns a 400 error with a `WorkflowParseError` message such as `"Invalid workflow structure"` or `"Failed to parse workflow JSON"`.

**Root cause:** The input file is not valid n8n workflow JSON, is missing required top-level fields (`nodes`, `connections`), or contains malformed JSON syntax.

**Resolution:**

1. Validate the JSON syntax using a tool like `python -m json.tool workflow.json`.
2. Ensure the file was exported from n8n using **Workflow > Download as JSON** (not copied from the editor URL).
3. Confirm the exported JSON contains `nodes` and `connections` arrays at the top level.
4. If the workflow was manually edited, check for trailing commas, unquoted keys, or missing brackets.

### Validation error on workflow payload

**Symptoms:** The analyzer returns a 400 response with `"Validation error"` and details about missing or invalid fields.

**Root cause:** The workflow payload does not conform to the expected Pydantic model schema. Required fields may be missing or have incorrect types.

**Resolution:**

1. Check the error detail for the specific field that failed validation.
2. Ensure each node has the required fields: `id`, `type`, `name`, `parameters`, and `position`.
3. Ensure connections reference valid node names that exist in the `nodes` array.

### Low confidence score in conversion report

**Symptoms:** The analysis report returns a `confidence_score` significantly below 1.0, or lists many `blocking_issues`.

**Root cause:** The workflow contains nodes that are unsupported or only partially supported by the translation engine.

**Resolution:**

1. Review the `unsupported_nodes` list in the report to identify which nodes cannot be translated.
2. Check [`docs/supported-node-types.md`](supported-node-types.md) for the current support matrix.
3. Consider simplifying the workflow by replacing unsupported nodes with supported alternatives before conversion.
4. For unsupported nodes, the AI agent fallback service (TASK-0008) can attempt automatic translation.

### Payload analysis warnings

**Symptoms:** The analysis report includes warnings such as `unbounded_list`, `large_static_payload`, `large_map_state`, or `accumulation_risk`.

**Root cause:** The workflow contains patterns that may exceed AWS Step Functions payload limits (256 KB per state).

**Resolution:**

- **`unbounded_list`:** Add explicit limits to operations that fetch lists of items. Step Functions has a 256 KB payload limit per state transition.
- **`large_static_payload`:** Move large hardcoded data to S3 or DynamoDB and reference it at runtime instead of embedding it in the state machine definition.
- **`large_map_state`:** Reduce the number of items processed in a single Map state, or use Distributed Map with an S3 data source.
- **`accumulation_risk`:** Refactor the workflow to avoid accumulating data through multiple steps. Use intermediate storage (S3, DynamoDB) for large datasets.

---

## Translation Issues

### Unsupported node type warning

**Symptoms:** Translation output includes a warning mentioning an unsupported node type, or the node is translated as a placeholder Pass state.

**Root cause:** The node type is not in any translator's dispatch table. See the `NodeClassification` enum value `UNSUPPORTED`.

**Resolution:**

1. Check [`docs/supported-node-types.md`](supported-node-types.md) for the list of supported node types and their translation targets.
2. If the AI agent fallback service is enabled (TASK-0008), unsupported nodes are automatically translated using an LLM. Review the generated state for correctness.
3. For nodes not handled by the fallback, manually implement the equivalent Step Functions state in the generated ASL output.

### Expression translation failure

**Symptoms:** An `ExpressionTranslationError` is raised with a message like `"Failed to translate expression"`. The error includes the original n8n expression that could not be converted.

**Root cause:** The n8n expression uses JavaScript syntax or built-in functions that have no direct equivalent in JSONata (the expression language used by Step Functions).

**Resolution:**

1. Check the `expression` field in the error to identify the problematic expression.
2. Common untranslatable patterns include:
   - Complex JavaScript method chains (e.g., `.map().filter().reduce()`)
   - n8n-specific helper functions (e.g., `$prevNode`, `$workflow`)
   - Regular expressions or string manipulation using JS-specific APIs
3. Simplify the expression in the original n8n workflow, or plan to implement the logic in a Lambda function post-conversion.
4. See TASK-0024 for ongoing work to expand expression translation coverage.

### ASL validation error during translation

**Symptoms:** An `ASLValidationError` is raised after translation with a list of `violations` describing schema conformance issues.

**Root cause:** The generated Amazon States Language definition does not conform to the ASL JSON Schema. This typically indicates a bug in a translator or an edge case in the workflow structure.

**Resolution:**

1. Review the `violations` list to identify which states or fields are invalid.
2. Common violations include:
   - Missing `End` or `Next` field on a state
   - Invalid state type names
   - Malformed JSONata expressions in `Parameters` or `ResultSelector`
3. If the violation points to a specific translated node, check whether the original n8n node has unusual configuration.
4. Report persistent ASL validation errors as a bug, including the original workflow JSON and the full error output.

---

## Packaging Issues

### CDK synth fails with ImportError

**Symptoms:** Running `cdk synth` in the generated project directory fails with a Python `ImportError` or `ModuleNotFoundError`.

**Root cause:** The required CDK dependencies are not installed in the current Python environment.

**Resolution:**

1. Navigate to the generated CDK project directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install the project dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Retry `cdk synth`.

### ASL schema validation failure during packaging

**Symptoms:** The packager raises an `ASLValidationError` with a list of `errors` during the `_step_validate_asl` phase.

**Root cause:** The ASL definition passed to the packager does not conform to the ASL JSON Schema. This is separate from the translation-stage validation and catches issues introduced between translation and packaging.

**Resolution:**

1. Review the `errors` list for specific schema violations.
2. If you manually edited the ASL definition after translation, validate it against `docs/asl_schema.json`:
   ```bash
   python -c "
   import json, jsonschema
   schema = json.load(open('docs/asl_schema.json'))
   asl = json.load(open('definition.asl.json'))
   jsonschema.validate(asl, schema)
   "
   ```
3. Fix any schema violations and re-run the packager.

### Lambda package generation failure

**Symptoms:** The packager fails during the `_step_write_lambdas` phase with an error writing Lambda function code or layers.

**Root cause:** Code node translation produced invalid Python or JavaScript, or the Lambda handler template could not be rendered.

**Resolution:**

1. Check the generated Lambda function code in the output directory under the `lambdas/` folder.
2. Verify the code syntax: `python -c "import ast; ast.parse(open('handler.py').read())"` for Python handlers.
3. For JavaScript code nodes, ensure the translated code is compatible with the Node.js Lambda runtime.
4. If the code node uses n8n runtime globals (`$input`, `$json`, `$items`), see TASK-0014 for details on how these are shimmed in the Lambda environment.

### Missing IAM permissions in generated policy

**Symptoms:** The generated IAM policy in the CDK stack uses overly broad wildcard ARNs or is missing required service permissions.

**Root cause:** The IAM policy generator infers permissions from the ASL definition, but may not detect all required actions, especially for custom Lambda functions or less common AWS service integrations.

**Resolution:**

1. Review the generated IAM policy in the CDK stack file.
2. Follow the principle of least privilege: replace wildcard ARNs (`arn:aws:{service}:*:*:*`) with specific resource ARNs for your AWS account and region.
3. See TASK-0009 for details on IAM wildcard ARN improvements.
4. For custom Lambda functions, ensure the state machine execution role has `lambda:InvokeFunction` permission on the specific function ARNs.

---

## Deployment Issues

### CDK bootstrap required

**Symptoms:** `cdk deploy` fails with a message about the CDK toolkit stack not being found, or `"This stack uses assets, so the toolkit stack must be deployed"`.

**Root cause:** The AWS account and region have not been bootstrapped for CDK deployments.

**Resolution:**

1. Run CDK bootstrap for your target account and region:
   ```bash
   cdk bootstrap aws://ACCOUNT_ID/REGION
   ```
2. Ensure your AWS credentials have sufficient permissions to create the bootstrap resources (S3 bucket, IAM roles).
3. Retry `cdk deploy`.

### CloudFormation stack creation fails

**Symptoms:** `cdk deploy` fails with a CloudFormation error during stack creation or update. Common errors include resource limit exceeded, invalid resource properties, or dependency conflicts.

**Root cause:** The generated CloudFormation template contains a resource configuration that is incompatible with your AWS account limits or region availability.

**Resolution:**

1. Check the CloudFormation console for the specific error event on the failed resource.
2. Common failures:
   - **Lambda function size limit:** The packaged Lambda deployment exceeds the 50 MB (zipped) or 250 MB (unzipped) limit. Reduce dependencies or use Lambda layers.
   - **IAM role creation limit:** You have reached the maximum number of IAM roles in your account. Request a limit increase or clean up unused roles.
   - **Region availability:** Some AWS services used in the generated stack may not be available in your target region.
3. Fix the resource configuration and redeploy.

### SSM parameter setup required

**Symptoms:** The deployed state machine fails immediately because SSM parameters for credentials are not populated.

**Root cause:** The packager generates SSM Parameter Store placeholders for credentials (API keys, OAuth tokens), but does not populate them. These must be configured manually before the state machine can execute.

**Resolution:**

1. Check the generated `CREDENTIALS.md` file in the output directory for the list of required SSM parameters and setup instructions.
2. For each parameter, follow the linked documentation to obtain the credential and store it in SSM:
   ```bash
   aws ssm put-parameter \
     --name "/phaeton/<workflow>/<credential-name>" \
     --type SecureString \
     --value "your-credential-value"
   ```
3. For OAuth2 credentials, you will need both the access token and refresh token parameters.
4. See TASK-0018 for detailed credential setup documentation.

---

## Runtime Issues

### State machine execution fails with States.Runtime error

**Symptoms:** The Step Functions execution fails with a `States.Runtime` error on a specific state, often with a message about JSONata evaluation or data type issues.

**Root cause:** A JSONata expression in the state definition evaluated to an unexpected type or failed to resolve an input path.

**Resolution:**

1. Open the failed execution in the Step Functions console and inspect the input/output of the failed state.
2. Check the JSONata expression for type assumptions. Common issues:
   - Accessing a field that does not exist in the input (returns `undefined` instead of the expected value).
   - Arithmetic operations on string values that should be numbers.
   - Array operations on scalar values or vice versa.
3. Test the JSONata expression using the [JSONata Exerciser](https://try.jsonata.org/) with sample input data.
4. Update the ASL definition to handle missing fields with JSONata defaults (e.g., `$.field ? $.field : "default"`).

### State machine execution fails with States.TaskFailed

**Symptoms:** A Task state fails with `States.TaskFailed`. The error detail may include an AWS service error such as `AccessDeniedException`, `ResourceNotFoundException`, or a Lambda invocation error.

**Root cause:** The underlying AWS service call made by the Task state failed. This is distinct from a state machine definition error.

**Resolution:**

- **AccessDeniedException:** The state machine execution role lacks the required IAM permission. See [Missing IAM permissions](#missing-iam-permissions-in-generated-policy) above.
- **ResourceNotFoundException:** The target resource (Lambda function, DynamoDB table, S3 bucket) does not exist in the target account/region. Verify the resource ARN in the state definition.
- **Lambda invocation error:** Check the Lambda function's CloudWatch Logs for the execution error. Common causes include missing environment variables, import errors in the handler, or timeout.

### State machine execution times out

**Symptoms:** The Step Functions execution reaches the `TimeoutSeconds` limit and is aborted with a `States.Timeout` error.

**Root cause:** A Task state or the overall state machine took longer than the configured timeout. Default Step Functions timeout is 1 year for Standard workflows, but individual states may have shorter timeouts set during translation.

**Resolution:**

1. Identify which state timed out from the execution history.
2. For Lambda tasks, check if the Lambda function itself is timing out (default 3 seconds). Increase the Lambda timeout in the CDK stack if needed.
3. For service integration tasks (e.g., waiting for a long-running job), consider using `.sync` integration patterns or increasing the state timeout.
4. For the overall workflow, ensure the state machine type (Standard vs. Express) matches your execution duration needs. Express workflows have a maximum duration of 5 minutes.

### Data format mismatch between states

**Symptoms:** A state receives input in an unexpected format, causing JSONata expressions or service API calls to fail. The previous state's output does not match the next state's expected input shape.

**Root cause:** n8n passes data between nodes in a specific format (`items` array with `json` property), while Step Functions passes raw JSON between states. The translation may not fully normalize data shapes across all state transitions.

**Resolution:**

1. Inspect the execution history to compare the output of the upstream state with the input of the failing state.
2. Add a Pass state with `Parameters` or `ResultSelector` to reshape the data between incompatible states.
3. Common format mismatches:
   - n8n array-of-items format (`[{"json": {...}}]`) vs. plain object or array.
   - Nested result wrappers from AWS service integrations (e.g., DynamoDB responses include metadata).
   - Map state output is always an array, even if the original n8n workflow expected a single item.

---

## Error Message Reference

| Error Message | Stage | Description | See Section |
|---|---|---|---|
| `WorkflowParseError: Failed to parse workflow JSON` | Analysis | Input file is not valid n8n workflow JSON | [Workflow JSON fails to parse](#workflow-json-fails-to-parse) |
| `Validation error` (400) | Analysis | Workflow payload missing required fields | [Validation error on workflow payload](#validation-error-on-workflow-payload) |
| `UnsupportedNodeError: <node_type>` | Translation | Node type has no registered translator | [Unsupported node type warning](#unsupported-node-type-warning) |
| `ExpressionTranslationError: Failed to translate expression` | Translation | n8n expression cannot be converted to JSONata | [Expression translation failure](#expression-translation-failure) |
| `ASLValidationError: <violations>` | Translation / Packaging | Generated ASL does not conform to schema | [ASL validation error](#asl-validation-error-during-translation) |
| `PackagerError` | Packaging | General packaging pipeline failure | [Packaging Issues](#packaging-issues) |
| `ImportError: No module named 'aws_cdk'` | Packaging | CDK dependencies not installed | [CDK synth fails with ImportError](#cdk-synth-fails-with-importerror) |
| `This stack uses assets, so the toolkit stack must be deployed` | Deployment | CDK bootstrap not run | [CDK bootstrap required](#cdk-bootstrap-required) |
| `States.Runtime` | Runtime | JSONata expression evaluation failure | [States.Runtime error](#state-machine-execution-fails-with-statesruntime-error) |
| `States.TaskFailed` / `AccessDeniedException` | Runtime | IAM permission missing for service call | [States.TaskFailed](#state-machine-execution-fails-with-statestaskfailed) |
| `States.Timeout` | Runtime | State or execution exceeded timeout | [Execution times out](#state-machine-execution-times-out) |

---

## Related Resources

- [Getting Started Guide](getting-started.md) -- Installation, quick start, and initial setup.
- [Supported Node Types](supported-node-types.md) -- Complete list of translatable n8n node types.
- TASK-0008 -- AI agent fallback for unsupported node types.
- TASK-0009 -- IAM wildcard ARN improvements.
- TASK-0014 -- Code node n8n runtime globals shimming.
- TASK-0018 -- Credential setup documentation.
- TASK-0024 -- Complex expression translation coverage.
