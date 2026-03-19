# Create Translator Deployment Stacks

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #14

## Overview

The current `AiAgentStack` deploys a single Lambda that handles both node and expression translation. With the ai-agent split into two independent components, two new CDK stacks are needed: `NodeTranslatorStack` and `ExpressionTranslatorStack`. Each deploys one Lambda with Bedrock `InvokeModel` permissions.

Both Lambdas use: Python 3.13, ARM64 architecture, 1024 MB memory, 120-second timeout.

## Dependencies

- **Blocked by:** TASK-0004 (node-translator package must exist for code asset), TASK-0005 (expression-translator package must exist for code asset)
- **Blocks:** TASK-0017 (app.py wiring), TASK-0019 (Lambda code asset exclusions)

## Acceptance Criteria

1. `node_translator_stack.py` exists and defines a `NodeTranslatorStack` with a Lambda function.
2. `expression_translator_stack.py` exists and defines an `ExpressionTranslatorStack` with a Lambda function.
3. Lambda function names: `phaeton-node-translator` and `phaeton-expression-translator`.
4. Both Lambdas have Bedrock `InvokeModel` IAM permissions.
5. Both use Python 3.13, ARM64, 1024 MB memory, 120s timeout.
6. Each stack exposes its Lambda function as a property (for cross-stack references).
7. No CDK alpha constructs are used (stable `aws_cdk.aws_lambda` only).
8. `uv run pytest` passes in `deployment/`.
9. `uv run ruff check` passes in `deployment/`.

## Implementation Details

### Files to Modify

- `deployment/stacks/node_translator_stack.py` (new)
- `deployment/stacks/expression_translator_stack.py` (new)

### Technical Approach

1. **Read `deployment/stacks/ai_agent_stack.py`** to understand the current pattern: Lambda configuration, Bedrock permissions, code asset path, environment variables.

2. **Create `node_translator_stack.py`:**
   ```python
   class NodeTranslatorStack(cdk.Stack):
       def __init__(self, scope, construct_id, **kwargs):
           super().__init__(scope, construct_id, **kwargs)
           self.function = lambda_.Function(
               self, "NodeTranslatorFunction",
               function_name="phaeton-node-translator",
               runtime=lambda_.Runtime.PYTHON_3_13,
               architecture=lambda_.Architecture.ARM_64,
               memory_size=1024,
               timeout=cdk.Duration.seconds(120),
               handler="phaeton_node_translator.handler.handler",
               code=lambda_.Code.from_asset("../node-translator/src"),
           )
           # Add Bedrock InvokeModel permissions
   ```

3. **Create `expression_translator_stack.py`:** Same pattern, pointing to `expression-translator/src` and `phaeton_expression_translator.handler.handler`.

4. Follow the existing stack patterns in the deployment directory for consistency (bundling options, environment variables, tags, etc.).

### Testing Requirements

- CDK synthesis tests should verify both stacks produce valid CloudFormation.
- Verify Lambda function names, runtime, architecture, memory, and timeout in synthesized template.
- Verify Bedrock IAM policy is attached.
