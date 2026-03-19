# Phaeton Component Restructuring — Gap Analysis

## Executive Summary

The Phaeton codebase has several structural concerns that need to be addressed to support the managed pipeline architecture. The ai-agent component performs two distinct tasks (node translation and expression translation) and should be split into independent components. Spec file management is coupled into the release-parser instead of being its own concern. An empty `src/phaeton_integration_tests/` directory exists alongside the real `tests/integration/`. CLI and Lambda handler code are tangled rather than following a clean ports-and-adapters pattern where core logic is interface-agnostic. Documentation references CLIs as the primary interface when everything should be Lambda-first for Step Functions, Lambda Function URLs, and API Gateway integration.

### Architectural Principles

The system is a collection of **loosely coupled microservices**, not a distributed monolith. All restructuring must preserve this:

- **Event-driven where possible**: Use S3 events and EventBridge for async inter-service communication. Components react to events ("spec file uploaded"), not commands ("rebuild the index").
- **Sync invocation only where immediate response is required**: The translation engine's synchronous Lambda invoke of AI agents is acceptable because it needs the result to continue. Step Functions orchestration of the pipeline is acceptable for the same reason.
- **Each service owns its domain models**: Internal models are private. Cross-service communication uses JSON contracts.
- **phaeton-models for boundary contracts only**: Shared contract models (enums, value objects at service boundaries) live here. Keep it lean — do not add internal domain models, utilities, or business logic. Every addition should answer: "Is this a contract type that multiple services exchange?"
- **No service-to-service code imports**: Services never import from each other's packages. They communicate via Lambda invocation (JSON in/out), S3 objects, or events.

### Effort Key

| Size | Description |
|------|-------------|
| XS | < 1 hour, single file, mechanical change |
| S | 1–3 hours, few files, straightforward |
| M | 3–8 hours, multiple files, some design decisions |
| L | 1–2 days, new component or significant refactor |
| XL | 2+ days, cross-cutting changes, many files |

---

## P0 — Foundation (Shared Models and Cleanup)

### 1. Add Confidence Enum to phaeton-models

**Effort: XS**

The `Confidence` enum (HIGH, MEDIUM, LOW) is currently defined in `ai-agent/src/phaeton_ai_agent/models.py` and consumed across component boundaries by `n8n-to-sfn`. It needs to be in the shared models package so both new AI agent components and the translation engine can import it without cross-component coupling.

Add a `Confidence` StrEnum to `phaeton-models`. Update existing imports in `ai-agent/` and `n8n-to-sfn/` to reference the shared location.

**Files:**
- `shared/phaeton-models/src/phaeton_models/confidence.py` (new)
- `shared/phaeton-models/src/phaeton_models/__init__.py`
- `ai-agent/src/phaeton_ai_agent/models.py` (remove local Confidence)
- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py`

### 2. Move Spec Models to phaeton-models

**Effort: S**

The spec-related Pydantic models (`ApiSpecEntry`, `ApiSpecIndex`, `SpecEndpoint`, `NodeApiMapping`) are currently defined in `n8n-release-parser/src/n8n_release_parser/models.py`. They will be consumed by the new `spec-registry` component and potentially by the release-parser for reading index data. Moving them to `phaeton-models` avoids circular dependencies.

Extract these frozen Pydantic models into a new submodule in phaeton-models. Update all imports in `n8n-release-parser/` (spec_index.py, matcher.py, cli.py, tests).

**Files:**
- `shared/phaeton-models/src/phaeton_models/spec.py` (new)
- `shared/phaeton-models/src/phaeton_models/__init__.py`
- `n8n-release-parser/src/n8n_release_parser/models.py` (remove spec models)
- `n8n-release-parser/src/n8n_release_parser/spec_index.py` (update imports)
- `n8n-release-parser/src/n8n_release_parser/matcher.py` (update imports)
- `n8n-release-parser/src/n8n_release_parser/cli.py` (update imports)

### 3. Delete Empty src/phaeton_integration_tests/

**Effort: XS**

`src/phaeton_integration_tests/` contains only `__init__.py`. All real integration tests live in `tests/integration/`. This empty directory is confusing and should be removed.

Delete the directory and remove any references in root `pyproject.toml`.

**Files:**
- `src/phaeton_integration_tests/` (delete)
- `pyproject.toml` (check for references)

---

## P0 — New Components (Depend on Foundation)

### 4. Create Node Translator Component

**Effort: L**

Split the node translation responsibility out of `ai-agent/` into an independent `node-translator/` component. This agent translates n8n workflow nodes into AWS Step Functions ASL states using Strands Agents with Bedrock.

The new component gets its own Strands Agent singleton with a system prompt tailored specifically for node translation (the current shared prompt is generic). The handler accepts a flat request (no `operation` routing). Utility functions `_generate_tag_suffix()` (~5 lines) and `_parse_json_response()` (~15 lines) are duplicated from the original — they're small and agent-specific.

Design with ports-and-adapters from the start: core logic in `agent.py`, Lambda handler adapter in `handler.py`, dev-only CLI adapter in `cli.py`.

Source material: `ai-agent/src/phaeton_ai_agent/agent.py` (translate_node function, _validate_asl_states, NODE_PROMPT_TEMPLATE), `ai-agent/src/phaeton_ai_agent/models.py` (NodeTranslationRequest, AIAgentResponse), `ai-agent/src/phaeton_ai_agent/handler.py` (translate_node branch), `ai-agent/tests/test_agent.py` (node translation tests), `ai-agent/tests/test_handler.py` (node handler tests).

**Files:**
- `node-translator/pyproject.toml` (new)
- `node-translator/src/phaeton_node_translator/__init__.py` (new)
- `node-translator/src/phaeton_node_translator/agent.py` (new)
- `node-translator/src/phaeton_node_translator/models.py` (new)
- `node-translator/src/phaeton_node_translator/handler.py` (new)
- `node-translator/src/phaeton_node_translator/cli.py` (new, dev-only)
- `node-translator/tests/test_agent.py` (new)
- `node-translator/tests/test_handler.py` (new)
- `node-translator/tests/test_models.py` (new)
- `node-translator/tests/conftest.py` (new)

### 5. Create Expression Translator Component

**Effort: L**

Split the expression translation responsibility out of `ai-agent/` into an independent `expression-translator/` component. This agent translates n8n expressions (e.g., `{{ $json.field }}`) into JSONata expressions for Step Functions.

The new component gets its own Strands Agent with a system prompt tailored specifically for expression translation (JSONata output, not ASL). The handler accepts a flat request (no `operation` routing). Utility functions duplicated as in item 4.

Design with ports-and-adapters from the start.

Source material: `ai-agent/src/phaeton_ai_agent/agent.py` (translate_expression function, EXPRESSION_PROMPT_TEMPLATE), `ai-agent/src/phaeton_ai_agent/models.py` (ExpressionTranslationRequest, ExpressionResponse), `ai-agent/src/phaeton_ai_agent/handler.py` (translate_expression branch), `ai-agent/tests/test_agent.py` (expression translation tests).

**Files:**
- `expression-translator/pyproject.toml` (new)
- `expression-translator/src/phaeton_expression_translator/__init__.py` (new)
- `expression-translator/src/phaeton_expression_translator/agent.py` (new)
- `expression-translator/src/phaeton_expression_translator/models.py` (new)
- `expression-translator/src/phaeton_expression_translator/handler.py` (new)
- `expression-translator/src/phaeton_expression_translator/cli.py` (new, dev-only)
- `expression-translator/tests/test_agent.py` (new)
- `expression-translator/tests/test_handler.py` (new)
- `expression-translator/tests/test_models.py` (new)
- `expression-translator/tests/conftest.py` (new)

### 6. Create spec-registry Component

**Effort: L**

Extract spec file management from `n8n-release-parser/` into a new `spec-registry/` component. The spec registry is a **standalone indexed registry of API specifications** that can grow independently of the nodes n8n supports. It owns the S3 bucket for API spec files, the index building logic, and spec-to-node matching.

Spec files are named to map to n8n node names (e.g., `n8n-nodes-base.Slack.json` for the Slack node). This naming convention is the contract between the registry and consumers — it enables lookup by node type without requiring a shared database.

Move `spec_index.py` logic (build_spec_index, normalize_base_url, auth detection, endpoint extraction, save/load index) and `matcher.py` (match_all_nodes) into the new component. The component provides a Lambda handler for index rebuilding **triggered by S3 events** — when a spec file is uploaded to the bucket, the Lambda reacts to the `s3:ObjectCreated` event and rebuilds the index. This is event-driven, not command-driven: uploaders don't need to know about the index. The component also includes a simple shell script for uploading spec files to S3 with consistent naming conventions (`aws s3 cp /path/to/file s3://<bucket>/<prefix>/<n8n-node-name>.json`).

Reuse the `StorageBackend` protocol pattern from release-parser (copy `storage.py` and `storage_s3.py` — they're generic).

Design with ports-and-adapters from the start.

**Files:**
- `spec-registry/pyproject.toml` (new)
- `spec-registry/src/spec_registry/__init__.py` (new)
- `spec-registry/src/spec_registry/indexer.py` (new — from spec_index.py)
- `spec-registry/src/spec_registry/matcher.py` (new — from matcher.py)
- `spec-registry/src/spec_registry/handler.py` (new)
- `spec-registry/src/spec_registry/cli.py` (new, dev-only)
- `spec-registry/src/spec_registry/storage.py` (new — StorageBackend protocol)
- `spec-registry/src/spec_registry/storage_s3.py` (new — S3 backend)
- `spec-registry/scripts/upload-spec.sh` (new)
- `spec-registry/tests/` (new — test_indexer.py, test_matcher.py, test_handler.py)

### 7. Refactor n8n-release-parser to Remove Spec Ownership

**Effort: M**

After spec-registry is created (item 6), remove spec-related code from `n8n-release-parser/`. The release-parser becomes a pure catalog producer: fetch n8n releases, parse node metadata, diff versions, build catalogs.

Remove `spec_index.py` and `matcher.py` modules. Remove `build-index` and `match` CLI commands from `cli.py`. Remove spec models from `models.py` (already moved to phaeton-models in item 2). Update all internal imports. Update tests that reference removed modules.

**Files:**
- `n8n-release-parser/src/n8n_release_parser/spec_index.py` (delete)
- `n8n-release-parser/src/n8n_release_parser/matcher.py` (delete)
- `n8n-release-parser/src/n8n_release_parser/cli.py` (remove spec commands)
- `n8n-release-parser/src/n8n_release_parser/models.py` (remove spec model imports if any remain)
- `n8n-release-parser/tests/test_spec_index.py` (delete or move to spec-registry)
- `n8n-release-parser/tests/test_matcher.py` (delete or move to spec-registry)

---

## P1 — Integration and Ports-and-Adapters Refactoring

### 8. Update AIAgentClient for Split Agents

**Effort: M**

`n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py` currently sends both `translate_node` and `translate_expression` operations to a single Lambda via `AI_AGENT_FUNCTION_NAME`. Update to invoke two separate Lambdas.

The client constructor should accept two function names. `translate_node()` invokes the node translator Lambda (payload is just the request fields — no `operation` wrapper). `translate_expression()` invokes the expression translator Lambda similarly.

Update `n8n-to-sfn/src/n8n_to_sfn/handler.py`'s `create_default_engine()` to read both `NODE_TRANSLATOR_FUNCTION_NAME` and `EXPRESSION_TRANSLATOR_FUNCTION_NAME` environment variables.

The `AIAgentProtocol` in `fallback.py` stays the same interface — only the client implementation changes.

**Files:**
- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py`
- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py` (verify protocol unchanged)
- `n8n-to-sfn/src/n8n_to_sfn/handler.py` (update env var reading)
- `n8n-to-sfn/tests/` (update client tests)

### 9. Delete Original ai-agent/ Component

**Effort: XS**

After the two new agent components are created (items 4, 5) and the client is updated (item 8), delete the original `ai-agent/` directory entirely.

Verify no remaining imports reference `phaeton_ai_agent` across the codebase.

**Files:**
- `ai-agent/` (delete entire directory)

### 10. Refactor n8n-release-parser Ports-and-Adapters

**Effort: M**

The release-parser handler currently only exposes `list_versions`. All other operations (fetch releases, diff catalogs, build catalog, generate report) are CLI-only. Create a `service.py` core layer that both CLI and handler call.

Move Typer from `dependencies` to `dev` dependency group in `pyproject.toml`. Ensure CLI module is not imported by handler. Handler should expose all operations via an `operation` field in the event.

**Files:**
- `n8n-release-parser/src/n8n_release_parser/service.py` (new)
- `n8n-release-parser/src/n8n_release_parser/handler.py`
- `n8n-release-parser/src/n8n_release_parser/cli.py`
- `n8n-release-parser/pyproject.toml` (move typer to dev deps)
- `n8n-release-parser/tests/test_handler.py`

### 11. Refactor workflow-analyzer Ports-and-Adapters

**Effort: S**

The handler already cleanly calls `analyzer.analyze_dict()`. Main issues: `analyze_and_render()` mixes core analysis with file I/O (writing reports), and Typer is a production dependency.

Split `analyze_and_render()` — core `analyze()` returns data, rendering/file writing stays in CLI adapter only. Move Typer to `dev` dependency group.

**Files:**
- `workflow-analyzer/src/workflow_analyzer/analyzer.py`
- `workflow-analyzer/src/workflow_analyzer/cli.py`
- `workflow-analyzer/pyproject.toml` (move typer to dev deps)

### 12. Refactor packager Ports-and-Adapters

**Effort: S**

The CLI in `__main__.py` is already fairly clean. Handler has S3 upload logic which is appropriate as a Lambda adapter concern. Main change: move Typer to `dev` dependency group.

**Files:**
- `packager/src/n8n_to_sfn_packager/__main__.py`
- `packager/pyproject.toml` (move typer to dev deps)

### 13. Add Dev CLI to n8n-to-sfn

**Effort: S**

The translation engine has no CLI currently — just a `__main__` block in `handler.py`. Create a proper dev-only Typer CLI that reads a JSON file, validates as `WorkflowAnalysis`, calls `engine.translate()`, and writes output.

Remove the `__main__` block from `handler.py`.

**Files:**
- `n8n-to-sfn/src/n8n_to_sfn/cli.py` (new)
- `n8n-to-sfn/src/n8n_to_sfn/handler.py` (remove __main__)
- `n8n-to-sfn/pyproject.toml` (add typer as dev dep, add project.scripts)

---

## P1 — Deployment Stack Updates

### 14. Create Translator Deployment Stacks

**Effort: M**

Replace single `AiAgentStack` with two independent stacks: `NodeTranslatorStack` and `ExpressionTranslatorStack`. Each deploys one Lambda with Bedrock `InvokeModel` permissions.

Lambda names: `phaeton-node-translator` and `phaeton-expression-translator`. Both use Python 3.13, ARM64, 1024 MB memory, 120s timeout.

**Files:**
- `deployment/stacks/node_translator_stack.py` (new)
- `deployment/stacks/expression_translator_stack.py` (new)

### 15. Update TranslationEngineStack for Split Agents

**Effort: S**

Update constructor to accept two function parameters (`node_translator_function` and `expression_translator_function`). Set two environment variables and grant invoke on both.

**Files:**
- `deployment/stacks/translation_engine_stack.py`

### 16. Create SpecRegistryStack

**Effort: M**

New CDK stack with: KMS-encrypted S3 bucket for spec files, Lambda handler for index rebuilding, S3 event notification triggering Lambda on `.json`/`.yaml` uploads.

**Files:**
- `deployment/stacks/spec_registry_stack.py` (new)

### 17. Update deployment/app.py and Delete Old Stack

**Effort: S**

Update `app.py` to import and wire the new stacks (two AI translator stacks, spec-registry stack). Remove `AiAgentStack` import. Wire both AI translator functions to `TranslationEngineStack`.

Delete `ai_agent_stack.py`.

**Files:**
- `deployment/app.py`
- `deployment/stacks/ai_agent_stack.py` (delete)

### 18. Update Deployment Tests

**Effort: M**

Update `deployment/tests/test_synth.py` assertions for the new stack structure: two AI translator Lambdas instead of one, spec-registry stack with S3 bucket and Lambda, updated TranslationEngineStack with two env vars.

**Files:**
- `deployment/tests/test_synth.py`

### 19. Update Lambda Code Assets

**Effort: S**

Ensure CDK `Code.from_asset()` paths exclude CLI modules from Lambda deployments. CLI modules are dev-only and should not be bundled. This may require adjusting asset paths or adding `.cdkignore`-style exclusions in the bundling options.

**Files:**
- `deployment/stacks/release_parser_stack.py`
- `deployment/stacks/workflow_analyzer_stack.py`
- `deployment/stacks/translation_engine_stack.py`
- `deployment/stacks/packager_stack.py`
- `deployment/stacks/node_translator_stack.py`
- `deployment/stacks/expression_translator_stack.py`
- `deployment/stacks/spec_registry_stack.py`

---

## P2 — Documentation Updates

### 20. Update Root CLAUDE.md

**Effort: S**

Update the repo structure diagram to reflect: `node-translator/`, `expression-translator/`, `spec-registry/` replacing `ai-agent/`. Remove `src/phaeton_integration_tests/`. Add guidance that CLIs are dev/testing only and Lambda functions are the primary interface.

**Files:**
- `CLAUDE.md`

### 21. Update Root README.md

**Effort: S**

Update component descriptions, remove CLI-as-primary-interface language. Document that all components expose Lambda handlers for Step Functions, Lambda Function URLs, and API Gateway. Document ports-and-adapters pattern.

**Files:**
- `README.md`

### 22. Update Architecture and Agent Documentation

**Effort: M**

Update `docs/architecture.md` to show split agents, spec-registry component, and ports-and-adapters pattern. Update or replace `docs/ai-agent.md` with documentation for both new AI translator components.

**Files:**
- `docs/architecture.md`
- `docs/ai-agent.md`

### 23. Update Component CLAUDE.md Files

**Effort: M**

Create CLAUDE.md files for new components (node-translator, expression-translator, spec-registry). Update existing component CLAUDE.md files to reflect ports-and-adapters pattern and dev-only CLI usage. Update `n8n-release-parser/CLAUDE.md` to remove spec references.

**Files:**
- `node-translator/CLAUDE.md` (new)
- `expression-translator/CLAUDE.md` (new)
- `spec-registry/CLAUDE.md` (new)
- `n8n-release-parser/CLAUDE.md`
- `workflow-analyzer/CLAUDE.md`
- `packager/CLAUDE.md`
- `n8n-to-sfn/CLAUDE.md`

### 24. Update Deployment Documentation

**Effort: S**

Update `docs/deployment.md` to reflect new stack structure, new Lambda functions, and spec-registry infrastructure.

**Files:**
- `docs/deployment.md`

---

## Recommended Sequencing

| Phase | Items | Dependencies |
|-------|-------|-------------|
| 1 — Foundation | 1, 2, 3 | None (parallelizable) |
| 2 — New Components | 4, 5, 6, 7 | 1→4,5; 2→6,7; 4∥5∥6; 6→7 |
| 3 — Integration | 8, 9, 10, 11, 12, 13 | 4,5→8→9; 10∥11∥12∥13 |
| 4 — Deployment | 14, 15, 16, 17, 18, 19 | 4,5→14; 8→15; 6→16; 14,15,16→17; 17→18; 10-13→19 |
| 5 — Documentation | 20, 21, 22, 23, 24 | All code changes complete |
