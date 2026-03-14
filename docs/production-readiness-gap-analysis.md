# Production Readiness Gap Analysis

## Executive Summary

Phaeton is a system of independent microservices for converting n8n workflows into deployable AWS Step Functions CDK applications:

1. **n8n Release Parser** — Extracts node type metadata from n8n npm packages
2. **Workflow Analyzer** — Classifies nodes and expressions in an n8n workflow JSON
3. **Translation Engine (n8n-to-sfn)** — Converts classified workflows into ASL state machine definitions
4. **Packager** — Generates a complete CDK application from the translation output

Each component is individually built and tested. However, **the system is not deployable as-is**. Components have contract mismatches that prevent data from flowing between them, runtime bugs that crash on import, and missing deployment and orchestration infrastructure. This document catalogs every known gap, organized by priority tier.

### Effort Key

| Size | Estimate |
|------|----------|
| XS | < 1 hour |
| S | 1-4 hours |
| M | 1-3 days |
| L | 1-2 weeks |
| XL | 2+ weeks |

---

## P0 — Blocks Any Deployment

These issues prevent the pipeline from producing a working output under any circumstances.

### 1. Inter-Component Contract Mismatch (Component 2 → Component 3)

**Effort: M**

Component 2 (Workflow Analyzer) outputs a `ConversionReport`. Component 3 (n8n-to-sfn) expects a `WorkflowAnalysis`. These are structurally incompatible models with no adapter between them.

**Top-level model mismatch:**

| Aspect | `ConversionReport` (Component 2) | `WorkflowAnalysis` (Component 3) |
|--------|-----------------------------------|-----------------------------------|
| Classified nodes | `list[ClassifiedNode]` with `.category` | `list[ClassifiedNode]` with `.classification` |
| Dependency graph | `graph_metadata: dict[str, Any]` (opaque dict) | `dependency_edges: list[DependencyEdge]` (structured) |
| Variables | absent | `variables_needed: dict[str, str]` |
| Expressions | top-level `classified_expressions` list | embedded per-node in `ClassifiedNode.expressions` |
| Payload warnings | `list[PayloadWarning]` (structured objects) | `list[str]` (plain strings) |
| Unsupported nodes | `list[ClassifiedNode]` (full objects) | `list[str]` (node names only) |

**`ClassifiedNode` field mismatch:**

| Component 2 (`classification.py`) | Component 3 (`analysis.py`) |
|------------------------------------|------------------------------|
| `category: NodeCategory` | `classification: NodeClassification` |
| `translation_strategy: str` | absent |
| `notes: str \| None` | absent |
| absent | `expressions: list[ClassifiedExpression]` |
| absent | `api_spec: str \| None` |
| absent | `operation_mappings: dict[str, Any] \| None` |

The enum class names differ (`NodeCategory` vs `NodeClassification`) though the values are identical. JSON serialized from Component 2 produces `{"category": "AWS_NATIVE"}` while Component 3 expects `{"classification": "AWS_NATIVE"}`.

**`ClassifiedExpression` field mismatch:**

| Field | Component 2 (`expression.py`) | Component 3 (`analysis.py`) |
|-------|-------------------------------|------------------------------|
| Expression text | `raw_expression` | `original` |
| Referenced nodes | `referenced_nodes` | `node_references` |
| Category values | `VARIABLE_REFERENCE`, `LAMBDA_REQUIRED` | `REQUIRES_VARIABLES`, `REQUIRES_LAMBDA` |

Only `JSONATA_DIRECT` matches across both expression category enums.

**Files:**
- `workflow-analyzer/src/workflow_analyzer/models/report.py` — `ConversionReport`
- `workflow-analyzer/src/workflow_analyzer/models/classification.py` — Component 2 `ClassifiedNode`
- `workflow-analyzer/src/workflow_analyzer/models/expression.py` — Component 2 `ClassifiedExpression`
- `n8n-to-sfn/src/n8n_to_sfn/models/analysis.py` — `WorkflowAnalysis`, Component 3 `ClassifiedNode`

### 2. Inter-Component Contract Mismatch (Component 3 → Component 4)

**Effort: S**

Component 3's `TranslationResult` uses uppercase enum values (`PYTHON`, `NODEJS`, `EVENTBRIDGE_SCHEDULE`, `LAMBDA_FURL`, `MANUAL`). Component 4's `PackagerInput` uses lowercase/different enum values (`python`, `nodejs`, `schedule`, `webhook`, `manual`, `app_event`). No mapping layer exists.

**Files:**
- `n8n-to-sfn/src/n8n_to_sfn/translators/base.py` — `LambdaRuntime`, `TriggerType`
- `packager/src/n8n_to_sfn_packager/models/inputs.py` — `LambdaRuntime`, `TriggerType`

### 3. Duplicated N8nNode Models

**Effort: S**

Two independent copies of `N8nNode` exist in separate packages. Fields are structurally identical today (same names, types, and aliases) but are separate Python classes. JSON round-tripping works, but any Python `isinstance` check or type annotation across package boundaries fails. As the components evolve independently, these models will diverge silently.

**Files:**
- `workflow-analyzer/src/workflow_analyzer/models/n8n_workflow.py` — `N8nNode`, `ConnectionTarget`, `WorkflowSettings`
- `n8n-to-sfn/src/n8n_to_sfn/models/n8n.py` — `N8nNode`, `N8nConnectionTarget`, `N8nSettings`

**Resolution:** Extract a shared `phaeton-models` package using Pydantic v2, or build an explicit adapter layer at each component boundary. All shared models must use Pydantic v2 for validation and serialization.

### 4. Python Syntax Error — Module Cannot Be Imported

**Effort: XS**

`iam_writer.py:211` contains Python 2 exception syntax:

```python
except ValueError, IndexError:
```

This should be `except (ValueError, IndexError):`. Python 3 raises a `SyntaxError` on this line, which means the **entire `iam_writer` module cannot be imported**. Any code path that touches `IAMPolicyGenerator` will crash immediately. This affects all packager operations that generate IAM policies for SDK-integrated state machines.

**File:** `packager/src/n8n_to_sfn_packager/writers/iam_writer.py:211`

### 5. EventBridge Schedule Rules Have No Targets

**Effort: S**

The `_wf_triggers()` method in `cdk_writer.py` generates `events.Rule(...)` constructs with a schedule expression but no `targets=` parameter. The generated code contains only a comment placeholder:

```python
# Target should reference the state machine
```

The `aws_events_targets` module is imported (line 206 of generated output) but never used. The resulting EventBridge rules will exist in AWS and fire on schedule but **invoke nothing**.

**File:** `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py:423-430` (method `_wf_triggers`)

### 6. EventBridge OAuth Rotation Rules Have No Targets

**Effort: S**

Same issue as above. The `_wf_oauth_rotation()` method generates schedule rules for OAuth token refresh but leaves a comment placeholder instead of attaching a Lambda target:

```python
# Target: oauth_refresh Lambda for {cred_name}
```

No `targets.LambdaFunction(...)` call is ever emitted, so the rotation schedule fires into the void.

**File:** `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py:444-453` (method `_wf_oauth_rotation`)

### 7. No Deployment or Service Orchestration

**Effort: M**

Phaeton is a system of independent microservices, not a single pipeline. Three capabilities are missing:

1. **Deployment infrastructure** — No IaC (CDK/CloudFormation) to deploy all components as services. Each component needs its own deployment stack with appropriate compute (Lambda, ECS, etc.).
2. **Release Parser trigger** — No mechanism to trigger the n8n Release Parser for an initial import of node metadata, then automatically after each new n8n release (e.g., via EventBridge scheduled rule or webhook).
3. **Workflow conversion flow** — When a user submits a workflow for conversion, it must pass through three stages in sequence: Workflow Analyzer → Translation Engine → Packager (to produce a downloadable CDK application). No event-driven orchestration exists to move a workflow through these stages (e.g., via SQS queues, Step Functions, or direct service invocation).

**Location:** Project-wide

---

## P1 — Required for Production (MVP: AWS-Centric Workflows)

These issues must be resolved before deploying workflows that primarily use AWS-native services (DynamoDB, SQS, SNS, S3, Lambda, etc.).

### 8. AI Agent Fallback Is a Stub — Needs Standalone Service

**Effort: L**

The `StubAIAgent` class raises `NotImplementedError` for both `translate_node()` and `translate_expression()`. Any workflow containing a node or expression that falls through to the AI agent path will crash the translation pipeline. A prompt template (`PROMPT_TEMPLATE`) is defined but never wired to an LLM. The `AITranslationResult` model wrapping confidence scores is also defined but unused.

This should be built as a new standalone component (Component 5) using the [AWS Strands Agents](https://strandsagents.com/) framework, deployed on [AWS AgentCore](https://aws.amazon.com/agentcore/). The Translation Engine would invoke this service when it encounters nodes or expressions it cannot translate with its built-in translators. The agent service would accept an `AIAgentProtocol`-compatible request and return a `TranslationResult`.

**File:** `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py:89-110`

### 9. IAM Policies Use Wildcard Resource ARNs

**Effort: M**

The `_collect_sdk_actions()` method constructs ARNs with empty region and account fields:

```python
resource_arn = f"arn:aws:{service.lower()}:::*"
```

This produces ARNs like `arn:aws:dynamodb:::*` — granting access to all resources of a service across all accounts and regions. Production IAM policies should scope resources to `arn:aws:{service}:{region}:{account-id}:{resource}` or at minimum `arn:aws:{service}:*:*:*`.

**File:** `packager/src/n8n_to_sfn_packager/writers/iam_writer.py:215`

### 10. Incomplete Observability — X-Ray and Instrumentation

**Effort: M**

The generated CDK stack lacks comprehensive observability. AWS X-Ray must be enabled across the entire stack to provide distributed tracing through Step Functions, Lambda functions, and SDK calls. Specifically:

- **Step Functions:** Enable X-Ray tracing on the state machine (`tracing_enabled=True`)
- **Lambda functions:** Enable active tracing and instrument the AWS SDK with the X-Ray SDK
- **Dead Letter Queues:** Attach SQS DLQs to the state machine and Lambda functions to capture failed executions for debugging and retry
- **CloudWatch Alarms:** Add alarms for `ExecutionsFailed`, `ExecutionsTimedOut`, and `ExecutionThrottled` metrics

Without X-Ray instrumentation, debugging failures across the multi-service execution flow is impractical.

**Location:** `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`

### 11. Execute Workflow Child ARN Is a Placeholder

**Effort: S**

The `_translate_execute_workflow` handler emits a `TaskState` with a Jinja-style placeholder for the child state machine ARN:

```python
"StateMachineArn": "{{ WorkflowArn['<workflow-id>'] }}"
```

This is not valid ASL and will fail at deploy time. Resolution strategy:
- **Same-stack references:** Use CDK context variables to resolve the child state machine ARN at synth time.
- **Cross-stack references:** Use SSM Parameters to store the child state machine ARN from the producing stack, and look it up via `ssm.StringParameter.value_for_string_parameter()` in the consuming stack.

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py:415-445`

### 12. Merge Node Emits Pass State Placeholder

**Effort: M**

The Merge node translator emits only a `PassState` with a warning: *"Merge node requires a Parallel state wrapping all upstream branches. This placeholder must be replaced during post-processing."* No post-processing step exists. Workflows with Merge nodes (joining parallel branches) will produce invalid state machines.

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py:317-335`

### 13. SplitInBatches Map State Has Placeholder Inner States

**Effort: M**

The SplitInBatches translator creates a `MapState` with `MaxConcurrency: 1` but the `ItemProcessor` contains only a single placeholder `PassState`. The warning states: *"inner workflow body must be inserted into the ItemProcessor.States block after full graph traversal."* No graph traversal post-processing step fills this in.

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py:284-315`

### 14. Code Node Handler Doesn't Validate n8n Runtime Globals

**Effort: M**

The Code node translator passes n8n JavaScript code into a Lambda handler template without validating or rewriting n8n-specific globals. The handler exposes `event.items` but does not inject `$input`, `$json`, `$items`, `$node`, or other n8n built-ins. Code referencing these globals will fail at runtime with `ReferenceError`. The translator emits a warning asking users to "review handler for n8n-specific globals" but performs no detection or transformation.

`luxon` is bundled as a dependency (hardcoded at line 52) but `DateTime` usage from `luxon` in user code is not validated against the Lambda Node.js runtime environment.

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/code_node.py:52, 185-187, 219-221`

### 15. Translation Engine Has No Service Entry Point

**Effort: S**

The `n8n-to-sfn` package is library-only. It has no `__main__.py`, no `cli.py`, and no `console_scripts` entry in `pyproject.toml`. As a microservice, it does not need a CLI — it needs a service entry point (e.g., Lambda handler or API endpoint) that the orchestration layer can invoke. For local development and testing, the library API can be exercised directly via `pytest`. The service entry point should accept a `WorkflowAnalysis` payload and return a `TranslationResult`.

**File:** `n8n-to-sfn/pyproject.toml`

### 16. No Integration Tests Against Real AWS

**Effort: L**

All tests are unit tests using mocks and fixtures. No test deploys a generated CDK stack to AWS, executes the resulting state machine, or validates the output. Without integration tests, there is no confidence that generated ASL is accepted by Step Functions, that IAM policies grant sufficient (but not excessive) permissions, or that Lambda functions execute correctly.

**Location:** All components

### 17. No CI/CD Pipeline

**Effort: M**

There are no GitHub Actions workflows and no automated quality gates beyond what individual component test suites provide. Each component uses `ruff` and `pytest` locally but there is no unified GitHub Actions pipeline that runs linting, type checking, and tests across all components on every push. CI/CD should be implemented using GitHub Actions with per-component workflows and a unified gate.

**Location:** Project-wide (no `.github/workflows/` directory)

### 18. Credential Setup Documentation Missing from Generated Package

**Effort: M**

All credentials are emitted as SSM `SecureString` parameters with placeholder values like `"<your-slack-oauth-token>"`. The user must provision fresh credentials for the new AWS deployment — migrating credentials from n8n is not recommended since switching systems is a natural rotation point.

The generated CDK application package needs to include clear documentation that:
- Lists every credential required by the workflow, with the SSM parameter path for each
- Links to the relevant service's credential creation page (e.g., AWS console, Slack app dashboard)
- Provides step-by-step instructions for populating each SSM parameter with the new credential values
- Warns that the workflow will fail if any placeholder values remain unreplaced

**Files:**
- `packager/src/n8n_to_sfn_packager/writers/ssm_writer.py` — generates placeholder parameters
- `packager/src/n8n_to_sfn_packager/models/ssm.py` — `SSMParameterDefinition` with `placeholder_value`
- `packager/src/n8n_to_sfn_packager/models/inputs.py:142-194` — `CredentialSpec`, `OAuthCredentialSpec`

### 19. Release Parser Has No Caching

**Effort: M**

The parser is entirely stateless. Every invocation of `extract_descriptions_from_package()` re-reads all `.node.json` files from disk and re-parses every node description via `parse_node_description()`. For the full n8n package (~400 node types), this is redundant work on every run. A SHA-256 hash comparison against previously parsed output would allow skipping unchanged nodes, saving compute time during incremental updates.

**File:** `n8n-release-parser/src/n8n_release_parser/parser.py:147, 203-233`

---

## P2 — Required for Broad Coverage (Any Public n8n Workflow)

These issues limit the breadth of n8n workflows that can be converted. They are not blockers for AWS-centric MVP workflows.

### 20. HTTP Request Node Not Supported

**Effort: L**

The HTTP Request node (`n8n-nodes-base.httpRequest`) is the most commonly used node in n8n workflows. It requires translation to either API Gateway + Lambda or direct SDK `HttpInvoke` patterns. Supporting authentication modes (API key, OAuth2, bearer token) adds complexity.

### 21. Set / Edit Fields Node Not Supported

**Effort: M**

The Set node (`n8n-nodes-base.set`) is used in most workflows for data transformation. It maps to a `PassState` with `Output` using JSONata expressions. All generated state machines must use the modern Step Functions JSONata query language — `ResultSelector` and `ResultPath` are part of the legacy JSONPath syntax and must not be used. The field mapping expressions need translation from n8n's format to JSONata.

### 22. Database Connector — Amazon Aurora (RDS Data API)

**Effort: L**

The initial version will only support Amazon Aurora databases with the RDS Data API (HTTP API) enabled. This avoids the need for VPC configuration, database drivers, and connection pooling — the RDS Data API is accessible via the AWS SDK as an HTTP endpoint. The translator should emit SDK integration states (`rds-data:ExecuteStatement`, `rds-data:BatchExecuteStatement`) rather than Lambda-backed handlers. Support for other databases (PostgreSQL, MySQL, MongoDB) is deferred to future iterations.

### 23. SaaS Integration Nodes Not Supported

**Effort: XL**

Nodes for Slack, Gmail, Google Sheets, Notion, Airtable, and dozens of other SaaS services are not supported. The PicoFun API strategy (wrapping each integration behind an API call) may address this at scale, but the PicoFun infrastructure itself does not exist yet.

### 24. Complex Expression Translation (Category C)

**Effort: L**

Expressions classified as `LAMBDA_REQUIRED` / `REQUIRES_LAMBDA` (Category C) require a Lambda function to evaluate. This depends on the AI agent being functional (see P1 issue #8). Until the AI agent works, any workflow with complex expressions that reference multiple upstream nodes or use JavaScript built-ins cannot be translated.

### 25. Loop Node Not Supported

**Effort: M**

The Loop node (`n8n-nodes-base.loop`) is distinct from SplitInBatches and requires a different Map/iterator pattern in Step Functions. Not currently in the dispatch table.

### 26. Form Trigger (Resumable Workflows)

**Effort: L**

The Form trigger (`n8n-nodes-base.formTrigger`) creates workflows that pause for human input. Step Functions supports this via callback patterns (`.waitForTaskToken`), but the current Wait translator sets `seconds = 0` for form submissions and webhooks — producing a degenerate WaitState that completes immediately rather than pausing.

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py:339-375`

### 27. Webhook Authentication

**Effort: M**

All webhook and callback handler Lambda Function URLs use `FunctionUrlAuthType.NONE`, making them publicly accessible without authentication. `AWS_IAM` auth is not appropriate here since webhook callers are external services. Authentication must be implemented within the Lambda function handler itself — e.g., HMAC signature verification, API key validation, or bearer token checking depending on the webhook source. The Function URL remains `NONE` auth, but the handler code must validate incoming requests before processing.

**File:** `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py:324-336`

### 28. VPC Configuration for Private Resources

**Effort: M**

Lambda functions that access RDS, ElastiCache, or other VPC-bound resources need VPC configuration (subnets, security groups). The packager generates no VPC-related CDK constructs. Workflows targeting private resources will fail with connection timeouts.

### 29. Custom Domain Support for Webhooks

**Effort: S**

Lambda Function URLs generate random AWS-assigned domains. For the initial version, Function URLs are sufficient. Custom domain support (via CloudFront or API Gateway) is deferred to a future iteration to avoid the additional complexity and configuration overhead that API Gateway introduces.

### 30. Lambda Layers for Shared Dependencies

**Effort: M**

Each generated Lambda function bundles its own dependencies. Workflows with multiple Code nodes or Lambda-backed integrations duplicate shared libraries (e.g., `luxon`, AWS SDK). Lambda Layers would reduce package sizes and cold start times.

---

## Testing and Documentation Gaps

### Testing

| Gap | Effort |
|-----|--------|
| No end-to-end tests (real n8n JSON → deployed Step Functions) | L |
| No contract tests between components (verifying model compatibility) | M |
| No `cdk synth` validation of generated CDK applications | S |
| No performance/load tests for large workflows (100+ nodes) | M |

### Documentation

| Gap | Effort |
|-----|--------|
| No user-facing getting-started guide | S |
| No supported node types reference | S |
| No troubleshooting guide | S |
| No architecture decision records (ADRs) | M |

---

## Summary by Priority

| Priority | Count | Total Effort |
|----------|-------|-------------|
| P0 — Blocks any deployment | 7 issues | ~2-3 weeks |
| P1 — Required for production MVP | 12 issues | ~2-3 months |
| P2 — Required for broad coverage | 11 issues | ~3-6 months |
| Testing & documentation | 8 gaps | ~1-2 months |

### Recommended Sequencing

1. **Week 1:** Fix P0 blockers — syntax error (XS), EventBridge targets (S+S), contract adapters (M+S), shared Pydantic v2 models (S)
2. **Weeks 2-4:** Address critical P1 items — IAM scoping, X-Ray instrumentation, service entry points, GitHub Actions CI/CD
3. **Months 2-3:** Complete remaining P1 — AI agent service (Strands Agents on AgentCore), Merge/SplitInBatches completion, integration tests, credential documentation, deployment infrastructure
4. **Months 3+:** P2 node coverage, driven by target workflow requirements
