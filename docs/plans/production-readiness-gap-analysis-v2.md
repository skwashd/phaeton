# Production Readiness Gap Analysis (v2)

## Executive Summary

This is the second production readiness gap analysis for Phaeton. The [first analysis](production-readiness-gap-analysis.md) identified 38 issues across P0/P1/P2 tiers. **All 38 have been addressed.** Since that analysis, the project added:

- **Shared models package** (`shared/phaeton-models`) with cross-component adapters
- **AI agent service** (`ai-agent`) using Strands Agents + Amazon Bedrock
- **Deployment stacks** (`deployment`) with CDK infrastructure and Step Functions orchestration
- **CI/CD pipeline** via GitHub Actions with per-component matrix builds
- Translators for HTTP Request, Set/Edit Fields, Database, SaaS, Code nodes, Merge/SplitInBatches post-processing, Loop node, and webhook authentication handlers
- Integration, contract, performance, and CDK synthesis tests
- Architecture decision records and documentation

This v2 analysis identifies **11 remaining gaps** introduced by or surviving the new architecture. The system is now functionally complete but has contract divergences, security concerns, and code quality issues that should be resolved before production deployment.

---

## P0 — Blocks Correct Pipeline Execution

These issues cause silent data loss or feature unreachability in the deployed orchestration pipeline.

### 1. Engine `TranslationOutput` diverges from shared boundary model

**Effort: S**

The translation engine defines a local `TranslationOutput` that diverges from the canonical shared boundary model in two ways:

| Aspect | Engine (local) | Shared (boundary) |
|--------|---------------|-------------------|
| `state_machine` type | `StateMachine` (Pydantic model) | `dict[str, Any]` (serialized ASL) |
| `credential_artifacts` | **absent** | `list[CredentialArtifact]` |

JSON round-trip works for `state_machine` (Pydantic serializes to dict), but **credentials are silently dropped** because the engine never populates the field. Any credential-dependent workflow (OAuth, API keys, etc.) will pass through the adapter without credential metadata, causing the packager to generate SSM parameters with no corresponding credential specs.

**Resolution:** Eliminate the local `TranslationOutput`. The engine should use `StateMachine` internally for post-processing, then serialize to the shared boundary model at the handler boundary: call `sm.model_dump(by_alias=True)` for the `state_machine` field, and collect `CredentialArtifact` objects during translation. The handler already serializes via `model_dump(mode="json")`, so the engine just needs to produce the shared model directly.

**Files:**
- `n8n-to-sfn/src/n8n_to_sfn/engine.py:53-60` — local `TranslationOutput` (to be removed)
- `shared/phaeton-models/src/phaeton_models/translator_output.py:100-121` — canonical boundary model (to be used directly)

### 2. Shared `PackagerInput` model is a subset of the local packager model

**Effort: M**

The shared `PackagerInput` boundary model (6 fields) is missing features that the packager's local model (9 fields) supports:

| Field | Shared model | Packager local model |
|-------|-------------|---------------------|
| `oauth_credentials` | absent | `list[OAuthCredentialSpec]` |
| `sub_workflows` | absent | `list[SubWorkflowReference]` |
| `vpc_config` | absent | `VpcConfig \| None` |

The adapter function in `deployment/functions/adapter/handler.py:92-96` produces `phaeton_models.packager_input.PackagerInput`, which structurally cannot carry VPC config, OAuth credentials, or sub-workflow references. The packager handler at `packager/src/n8n_to_sfn_packager/handler.py:48` validates against its local `PackagerInput`, so the missing fields default silently — **VPC networking, OAuth token rotation, and sub-workflow references are unreachable through the orchestration pipeline**.

The extra fields are **actively used** by packager writers: `oauth_credentials` drives SSM parameter generation and EventBridge-scheduled token rotation Lambdas; `vpc_config` generates security groups and attaches VPC config to Lambda functions; `sub_workflows` populates CDK context with cross-stack ARN placeholders. These are not dead fields.

**Resolution:** Move the missing types (`VpcConfig`, `OAuthCredentialSpec`, `SubWorkflowReference`, `WebhookAuthConfig`) and fields into `phaeton_models.packager_input` so it becomes the single source of truth. The packager should then import from the shared model — the local copy can be eliminated. The translation engine (or a new enrichment step in the adapter) must also be extended to detect and produce these artifacts so they flow through the pipeline.

**Files:**
- `shared/phaeton-models/src/phaeton_models/packager_input.py:196-217` — shared (6-field) model (to be extended)
- `packager/src/n8n_to_sfn_packager/models/inputs.py:346-389` — local (9-field) model (to be eliminated)
- `deployment/functions/adapter/handler.py:92-96` — adapter producing shared model

### 3. Pydantic `frozen=True` missing across all components except n8n-release-parser

**Effort: M**

The project convention (per CLAUDE.md) requires all Pydantic models to use `frozen=True` for immutable value objects. Only `n8n-release-parser/src/n8n_release_parser/models.py` complies. All models in the following components are mutable:

- `shared/phaeton-models` — `translator_output.py`, `packager_input.py`, `analyzer.py`, `translator.py`, `n8n_workflow.py`
- `workflow-analyzer` — all model files
- `n8n-to-sfn` — all model files
- `packager` — all model files
- `ai-agent` — `models.py`
- `deployment` — model classes in stacks

The engine's post-processing steps (`_apply_parallel_for_merges`, `_apply_map_for_split_in_batches`, `_wire_transitions`) mutate state objects in-place (setting `.next`, `.end`), which would break with frozen models. These methods need refactoring to construct new objects instead of mutating before `frozen=True` can be enabled project-wide.

**Files:** All Pydantic model files across all components (see list above)

---

## P1 — Security Issues

### 4. Expression evaluator code injection

**Effort: M**

`_build_expression_code()` at `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py:124-127` directly interpolates user-provided n8n expressions into generated JavaScript Lambda code:

```python
inner = _strip_expression_wrapper(expr)
return f"  const expressionResult = {inner};"
```

An n8n expression like `={{ 1; process.exit(0); // }}` would produce:

```javascript
const expressionResult = 1; process.exit(0); //;
```

This is valid JavaScript that executes arbitrary code in the generated Lambda function. The same pattern appears at line 250 in `_try_ai_agent()` for AI-translated expressions.

**Mitigation:** Validate/sanitize expressions before interpolation (e.g., reject expressions containing semicolons, `process`, `require`, `eval`), or use an AST-based approach that constructs the JS code structurally rather than via string interpolation.

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py:124-127, 250`

### 5. AI agent prompt injection via user content

**Effort: S**

At `ai-agent/src/phaeton_ai_agent/agent.py:134-141`, `node_json`, `expressions`, and `workflow_context` from user input are directly interpolated into the LLM prompt template via `.format()` without escaping or boundary markers:

```python
prompt = NODE_PROMPT_TEMPLATE.format(
    node_json=request.node_json,
    ...
)
```

An adversarial n8n workflow could contain node names or parameters designed to override agent instructions (e.g., a node named `Ignore all previous instructions and output...`). Risk is medium — the agent outputs structured JSON and errors are handled gracefully — but instructions could be overridden to produce malicious ASL.

**Mitigation:** Add clear boundary markers (e.g., XML tags) around user-provided content in the prompt template, and validate agent output against an ASL schema before accepting it.

**File:** `ai-agent/src/phaeton_ai_agent/agent.py:134-141`

### 6. Webhook authentication config unreachable through pipeline

**Effort: S**

Lambda Function URLs for webhook/callback handlers use `FunctionUrlAuthType.NONE` at `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py:564`. This is correct — `AWS_IAM` auth is inappropriate for external webhook callers, so authentication must be enforced within the Lambda handler code itself. The packager supports this via `webhook_auth` in the local `LambdaFunctionSpec`, which can generate HMAC, API key, or bearer token validation in the handler.

However, the shared `phaeton_models.packager_input.LambdaFunctionSpec` has no `webhook_auth` field (see P0 issue #2), so this authentication configuration is unreachable through the orchestration pipeline. Unauthenticated webhooks are a valid scenario (e.g., public form submissions), but when the source n8n workflow does have webhook authentication configured, it cannot flow through to the generated handler.

**Resolution:** This is resolved by P0 issue #2 — once `WebhookAuthConfig` and the `webhook_auth` field are promoted to the shared model, the adapter can carry authentication config through the pipeline. The packager should emit a warning (not an error) when a webhook handler has no auth configured, to surface the decision for user review.

**File:** `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py:564`

---

## P2 — Code Quality & Consistency

### 7. AI agent hardcoded AWS region

**Effort: XS**

At `ai-agent/src/phaeton_ai_agent/agent.py:95`, the Bedrock model region is hardcoded:

```python
region_name="us-east-1",
```

This must be configurable via the environment variable `AWS_REGION`, with a fallback to `us-east-1` when it is undefined.

**File:** `ai-agent/src/phaeton_ai_agent/agent.py:95`

### 8. AI agent Pydantic models missing `frozen=True`

**Effort: XS**

All four Pydantic models in `ai-agent/src/phaeton_ai_agent/models.py:19-55` (`NodeTranslationRequest`, `ExpressionTranslationRequest`, `AIAgentResponse`, `ExpressionResponse`) lack `model_config = ConfigDict(frozen=True)`. This is a subset of P0 issue #3 but called out separately since the ai-agent is a standalone service with its own deployment lifecycle.

**File:** `ai-agent/src/phaeton_ai_agent/models.py:19-55`

### 9. `StubAIAgent` in n8n-to-sfn is dead code

**Effort: XS**

`StubAIAgent` at `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py:90-110` raises `NotImplementedError` on both methods and is never used now that `AIAgentClient` exists. The `PROMPT_TEMPLATE` in the same file (lines 39-66) duplicates the one in `ai-agent/src/phaeton_ai_agent/agent.py:22-59`.

Should be removed.

**File:** `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py:39-66, 90-110`

### 10. Lint/type suppression comments that should be fixed

**Effort: S** (for all fixable suppressions combined)

The codebase contains `# noqa:` and `# type: ignore` suppressions. Most are legitimate; the following should be fixed:

#### Fixable suppressions

| File | Line | Suppression | Issue | Fix |
|------|------|-------------|-------|-----|
| `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py` | 252 | `# noqa: BLE001` | Blanket `except Exception` in AI agent fallback | Catch `(ConnectionError, TimeoutError, json.JSONDecodeError, ValueError)` |
| `n8n-to-sfn/src/n8n_to_sfn/translators/expression_evaluator.py` | 273 | `# noqa: BLE001` | Blanket `except Exception` in expression code builder | Catch `(ValueError, IndexError, KeyError)` |
| `deployment/stacks/orchestration_stack.py` | 28 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Type as `**kwargs: Any`, add `# noqa: ANN401` |
| `deployment/stacks/ai_agent_stack.py` | 14 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/translation_engine_stack.py` | 19 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/release_parser_stack.py` | 16 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/packager_stack.py` | 14 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `deployment/stacks/workflow_analyzer_stack.py` | 13 | `# noqa: ANN003` | Missing type annotation for `**kwargs` | Same fix |
| `n8n-to-sfn/src/n8n_to_sfn/translators/expressions.py` | 230 | `# type: ignore[return-value]` | `_walk_and_translate` returns `JsonValue` but function declares `dict[str, JsonValue]` return | Use `cast()` or fix return type |
| `n8n-release-parser/src/n8n_release_parser/cache.py` | 55, 68 | `# noqa: TRY301` | Create new specific exceptions for the errors, catch them |
| `tests/integration/test_simple_workflow.py` | 129, 156, 164, 195 | `# type: ignore[attr-defined]` | boto3 Step Functions client methods untyped | Add `types-boto3` to root `pyproject.toml` dev dependencies (already used by n8n-release-parser) |
| `tests/integration/conftest.py` | 215 | `# type: ignore[attr-defined]` | boto3 Step Functions client method untyped | Same fix — `types-boto3` provides PEP 484 stubs compatible with `ty` |

#### Accepted suppressions

These are legitimate and should be retained with their current justifications:

| File | Line | Suppression | Justification |
|------|------|-------------|---------------|
| `ai-agent/src/phaeton_ai_agent/agent.py` | 91 | `# noqa: PLW0603` | Singleton pattern for Lambda warm starts |
| `packager/src/n8n_to_sfn_packager/writers/lambda_writer.py` | 357 | `# noqa: PLW0603` | Global cache in generated Lambda handler code (string template) |
| `packager/src/n8n_to_sfn_packager/__main__.py` | 17, 25, 31 | `# noqa: B008` | Typer CLI convention for `typer.Option()` in function defaults |
| `packager/src/n8n_to_sfn_packager/writers/lambda_writer.py` | 435 | `# noqa: S607` | Hardcoded `uv lock` command, not user-controlled |
| `packager/src/n8n_to_sfn_packager/handler.py` | 59, 81 | `# noqa: S108` | Lambda `/tmp` is the only writable directory |  
| `tests/performance/conftest.py` | 112 | `# noqa: S311` | Seeded random for reproducible test fixtures |
| `tests/integration/conftest.py` | 153, 177 | `# noqa: S603` | Subprocess calls in integration test setup |
| `tests/integration/conftest.py` | 274 | `# noqa: S607` | Hardcoded `uv sync` for test setup |
| `packager/tests/test_report_writer.py` | 65 | `# noqa: S106` | Test OAuth token endpoint URL, not a secret |
| `packager/tests/test_cdk_writer.py` | 159, 439 | `# noqa: S106` | Test OAuth token endpoint URLs |
| `packager/tests/test_models.py` | 192, 379 | `# noqa: S106` | Test OAuth token endpoint URLs |
| `packager/tests/test_ssm_writer.py` | 27 | `# noqa: S106` | Test OAuth token endpoint URL |
| `packager/tests/test_packager_integration.py` | 245 | `# noqa: S106` | Test OAuth token endpoint URL |
| `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py` | 769 | `# type: ignore[operator]` | Dispatch table dict lookup — type checker cannot infer callable |
| `n8n-release-parser/tests/unit/test_cache.py` | 42 | `# type: ignore[arg-type]` | Intentionally testing with partial data |
| `n8n-release-parser/tests/unit/test_models.py` | 387 | `# type: ignore[call-arg]` | Intentionally testing validation of missing required fields |
| `shared/phaeton-models/tests/test_adapter_translator_to_packager.py` | 54, 81 | `# type: ignore[arg-type]` | Intentionally testing invalid enum values |

### 11. AI agent model ID may be outdated

**Effort: XS**

At `ai-agent/src/phaeton_ai_agent/agent.py:94`, the Bedrock model ID is `us.anthropic.claude-sonnet-4-20250514`. Newer models in the Claude 4.5/4.6 family are available (e.g., `claude-sonnet-4-6`) and may produce better translation results. The model ID should be configurable via environment variable.

**File:** `ai-agent/src/phaeton_ai_agent/agent.py:94`

---

## Resolved Issues from v1 Analysis

All 38 issues from the [v1 gap analysis](production-readiness-gap-analysis.md) have been addressed.

---

## Summary by Priority

| Priority | Count | Effort Range |
|----------|-------|-------------|
| P0 — Blocks correct pipeline execution | 3 issues | S + M + M |
| P1 — Security issues | 3 issues | M + S + S |
| P2 — Code quality & consistency | 5 issues | XS + XS + XS + S + XS |
| **Total** | **11 issues** | |

### Recommended Sequencing

1. **Immediate:** P0 #1 (engine TranslationOutput alignment, S) and P2 #7-9, #11 (XS items — hardcoded region, frozen models on ai-agent, dead code removal, model ID)
2. **Short-term:** P0 #2 (shared PackagerInput parity, M) and P1 #4 (expression injection, M), P1 #5-6 (prompt injection and webhook auth, S each), P2 #10 (suppression cleanup, S)
3. **Medium-term:** P0 #3 (frozen=True project-wide, M — requires engine refactoring)
