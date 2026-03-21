# PicoFun Integration Gap Analysis

## Executive Summary

The Phaeton end-to-end pipeline converts n8n workflows into deployable AWS Step Functions applications. The pipeline consists of: workflow-analyzer (classification), n8n-to-sfn (translation to ASL + Lambda artifacts), packager (CDK application generation), and shared phaeton-models (boundary models and adapters).

**PicoFun** (https://github.com/proactiveops/picofun) is a deterministic Python code generator that transforms OpenAPI 3.x and Swagger 2.0 specs into AWS Lambda handler code. It produces handlers that use the `picorun` runtime library for HTTP dispatch, along with Lambda layers and CDK constructs.

Currently, the `PicoFunTranslator` in `n8n-to-sfn` produces **placeholder** `LambdaArtifact` objects with comment-only handler code (see `n8n-to-sfn/src/n8n_to_sfn/translators/picofun.py:98-104`). No real code generation occurs. Similarly, the `ClassifiedNode.api_spec` and `ClassifiedNode.operation_mappings` fields exist in `phaeton_models/translator.py:92-93` but are never populated by the adapter. The packager has no awareness of PicoFun-specific artifacts (layers, CDK constructs).

**Goal**: Integrate the PicoFun library to generate real, deployable Lambda handler code from OpenAPI specs, wire the spec data through the adapter pipeline, and bundle PicoFun's layer and CDK construct support into the final packaged output.

### What Already Exists (reuse, don't rebuild)

| Existing | Location | Purpose |
|---|---|---|
| `ClassifiedNode.api_spec` / `.operation_mappings` | `phaeton_models/translator.py:92-93` | Fields exist but unpopulated |
| `ApiSpecEntry`, `ApiSpecIndex`, `NodeApiMapping` | `phaeton_models/spec.py` | Shared spec boundary models |
| `NodeApiMapping.operation_mappings` | `phaeton_models/spec.py:57` | Maps `"resource:operation"` → `"METHOD /path"` |
| `spec_registry.matcher.match_node_type()` | `spec-registry/src/spec_registry/matcher.py` | Matches node types to specs |
| `spec_registry.storage_s3.S3StorageBackend` | `spec-registry/src/spec_registry/storage_s3.py` | S3 read/write for spec files |
| `Spec.to_api_spec()` | PicoFun `picofun/spec.py:183` | Parses raw spec → `ApiSpec` IR (OpenAPI 3 + Swagger 2) |
| `LambdaGenerator.render(base_url, endpoint)` | PicoFun `picofun/lambda_generator.py:169` | Renders single endpoint → Python string |
| `Layer.prepare()` | PicoFun `picofun/layer.py:26` | Creates picorun layer directory |
| `CdkGenerator.generate()` | PicoFun `picofun/iac/cdk.py:18` | Generates CDK construct file |
| `get_parser()` / `discover_parsers()` | PicoFun `picofun/parsers/base.py` | Auto-detects Swagger 2 / OpenAPI 3 |
| `LambdaFunctionType.PICOFUN_API_CLIENT` | `phaeton_models/packager_input.py:28` | Enum value exists for PicoFun functions |
| `_infer_function_type()` | `phaeton_models/adapters/translator_to_packager.py` | Already maps "picofun" → `PICOFUN_API_CLIENT` |

### Effort Key

| Size | Meaning |
|---|---|
| XS | < 1 hour, single-file touch |
| S | 1–3 hours, 1–2 files |
| M | 3–6 hours, 2–4 files |
| L | 6–12 hours, 4+ files or complex logic |
| XL | 12+ hours, cross-component or infrastructure |

### Flagged PicoFun Upstream Changes

The following items require coordination with the PicoFun maintainer. They are not blocking — the Phaeton integration works around them — but addressing them would improve the library API for embedding:

1. **`render()` as stable public API**: Confirm `LambdaGenerator.render(base_url, endpoint)` is a stable library entrypoint. Consider exposing it as a top-level function for easier library use.
2. **Template path when installed as dep**: The CLI uses `importlib.resources.files("picofun")` (line 134 of `picofun/cli.py`). Confirm this resolves correctly when picofun is installed as a pip dependency in another project.
3. **Minimal Config for library use**: `picofun.config.Config` requires `output_dir` even when only using `render()`. Consider allowing `output_dir` to have a default or be optional for render-only usage.
4. **`CdkGenerator.generate()` return value**: Currently writes to disk, returns nothing. For library embedding, returning the rendered string (or the construct path) would help.
5. **PyPI release**: Stable release needed on PyPI for production dependency pinning.

---

## P0 — Core Translation Integration

### 1. Add picofun Dependency to n8n-to-sfn

**Effort: XS**

**File:** `n8n-to-sfn/pyproject.toml`

The `n8n-to-sfn` component needs the `picofun` package as a runtime dependency to call its code generation APIs. PicoFun requires Python >=3.13 (Phaeton requires >=3.14, which is compatible). PicoFun's pydantic==2.12.5 matches Phaeton's pinned version. Add `"picofun>=0.1.0"` to the `[project] dependencies` array.

### 2. Add spec_directory Field to TranslationContext

**Effort: XS**

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/base.py`

The `TranslationContext` model (line 59) needs a `spec_directory: str = ""` field. This is the local filesystem path where downloaded API spec files are cached. PicoFun's `Spec` class needs a file path to parse. The empty default preserves backward compatibility — when no spec directory is configured, the PicoFunTranslator falls back to placeholder code.

### 3. Create Spec Fetcher Module

**Effort: S**

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/spec_fetcher.py` (new)

API spec files are stored in S3 (uploaded by the spec-registry component). The translator needs to download them to a local temp directory before PicoFun can parse them. Create a `SpecFetcher` class that:

- Accepts `bucket`, `prefix` (default `"specs/"`), and `cache_dir` parameters
- Lazy-imports `boto3` to avoid hard dependency when running locally
- Downloads a spec file to `cache_dir` if not already cached
- Returns the local `Path` to the cached file
- Configured via `PHAETON_SPEC_BUCKET` / `PHAETON_SPEC_PREFIX` environment variables

```python
class SpecFetcher:
    def __init__(self, bucket: str, prefix: str = "specs/", cache_dir: str = "") -> None: ...
    def fetch(self, spec_filename: str) -> Path:
        """Download spec to cache_dir if not cached. Return local path."""
```

### 4. Create PicoFun Bridge Module

**Effort: M**

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_bridge.py` (new)

This module wraps PicoFun library calls, isolating the integration surface. It uses PicoFun's new IR models (`ApiSpec`, `Endpoint` from `picofun.models`) and the parser plugin system.

```python
class PicoFunBridge:
    def __init__(self, spec_directory: str = "") -> None: ...

    def load_api_spec(self, spec_filename: str, format_override: str | None = None) -> ApiSpec:
        """Parse spec file → PicoFun ApiSpec IR via Spec.to_api_spec()."""

    def find_endpoint(self, api_spec: ApiSpec, method: str, path: str) -> Endpoint | None:
        """Find matching Endpoint in the ApiSpec by method+path."""

    def render_endpoint(self, base_url: str, endpoint: Endpoint, namespace: str) -> str:
        """Render a single endpoint handler using LambdaGenerator.render(base_url, endpoint)."""
```

Key design decisions:
- Uses `Spec(spec_path).to_api_spec()` which auto-detects Swagger 2.0 vs OpenAPI 3.x via the parser plugin system
- Template path resolved via `importlib.resources.files("picofun")` (same pattern as PicoFun CLI line 134)
- `Config(auth_enabled=False)` since Phaeton manages auth via SSM/CredentialArtifacts
- `render()` takes `Endpoint` (the new PicoFun IR model), not raw dicts — signature is `LambdaGenerator.render(base_url: str, endpoint: Endpoint) -> str`

### 5. Create Operation Mapper Module

**Effort: S**

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_operation_mapper.py` (new)

Maps n8n node `resource`/`operation` parameters to HTTP `method + path` using `ClassifiedNode.operation_mappings`. The `operation_mappings` dict comes from `NodeApiMapping.operation_mappings` (`phaeton_models/spec.py:57`) which maps `"resource:operation"` → `"METHOD /path"` (e.g. `{"chat:postMessage": "POST /chat.postMessage"}`).

```python
def resolve_operation_to_endpoint(
    node_params: dict[str, Any],
    operation_mappings: dict[str, Any] | None,
) -> tuple[str, str] | None:
    """Map 'resource:operation' → (method, path). Returns None if unmapped."""
```

The function extracts `resource` and `operation` from `node_params`, forms the lookup key `"resource:operation"`, and searches `operation_mappings` for a match. Falls back to operation-only matching. Returns `None` when unmapped.

### 6. Rewrite PicoFunTranslator with Real Code Generation

**Effort: L**

**File:** `n8n-to-sfn/src/n8n_to_sfn/translators/picofun.py`

The current `PicoFunTranslator.translate()` (line 57) creates a `LambdaArtifact` with comment-only placeholder code at lines 98-107:

```python
lambda_artifact = LambdaArtifact(
    function_name=func_name,
    runtime=LambdaRuntime.PYTHON,
    handler_code=f"# PicoFun-generated client for {node.node.type}\n"
    f"# API spec: {node.api_spec or 'unknown'}\n"
    f"# This code is generated externally by PicoFun.\n",
    dependencies=[],
    directory_name=func_name,
)
```

Replace this with real code generation by:

1. Adding `__init__` accepting a `PicoFunBridge` instance (created in handler.py with spec_directory)
2. Adding `_generate_handler_code()` method that:
   - Resolves operation → `(method, path)` via the operation mapper using `node.operation_mappings`
   - Loads and parses the API spec via `bridge.load_api_spec(node.api_spec)`
   - Finds the matching `Endpoint` in the parsed `ApiSpec` via `bridge.find_endpoint(api_spec, method, path)`
   - Renders handler code via `bridge.render_endpoint(base_url, endpoint, namespace)`
   - Falls back to placeholder + warning on any failure (spec missing, operation unmapped, render error)
3. Setting `dependencies=["picorun", "requests", "aws-lambda-powertools"]` (plus `"boto3"` if credentials present)
4. Storing metadata: `picofun_spec`, `picofun_function_names`, `picofun_namespace` for use by the packager
5. **Graceful degradation**: if `api_spec` not set, or `spec_directory` empty, or any step fails → placeholder code + warning. The translator NEVER fails the pipeline.

### 7. Wire spec_directory into Engine and Handler

**Effort: S**

**Files:** `n8n-to-sfn/src/n8n_to_sfn/engine.py`, `n8n-to-sfn/src/n8n_to_sfn/handler.py`

In `engine.py`, add `spec_directory: str = ""` parameter to `TranslationEngine.__init__()` (line 59). Pass it through to the `TranslationContext` at line 71:

```python
context = TranslationContext(analysis=analysis, spec_directory=self._spec_directory)
```

In `handler.py`, update `create_default_engine()` (line 35) to:
- Read `PHAETON_SPEC_BUCKET` and `PHAETON_SPEC_PREFIX` environment variables
- If bucket is set: create a `SpecFetcher` instance with a temp directory as cache
- Create the `PicoFunBridge` with the spec_directory
- Pass `PicoFunBridge` to `PicoFunTranslator(bridge=bridge)` at line 61
- Pass `spec_directory` to `TranslationEngine`

---

## P1 — Adapter and Packager Integration

### 8. Populate api_spec and operation_mappings in Adapter

**Effort: M**

**File:** `shared/phaeton-models/src/phaeton_models/adapters/analyzer_to_translator.py`

The `convert_report_to_analysis()` function (line 55) currently does not populate `api_spec` or `operation_mappings` on `ClassifiedNode`. These fields exist in `phaeton_models/translator.py:92-93` but are always `None`.

Extend `convert_report_to_analysis()` to accept an optional parameter `node_spec_mappings: dict[str, dict[str, Any]] | None = None`. In `_convert_node()` (line 95), look up the node type (`cn.node.type`) in the mappings dict and populate `api_spec` and `operation_mappings` on the resulting `SfnClassifiedNode`.

This data originates from spec-registry's `matcher.match_all_nodes()` which returns `dict[str, ApiSpecEntry]`. The orchestration layer converts this to a plain dict before passing it to the adapter.

**Critical constraint**: phaeton-models is a leaf dependency and MUST NOT import from service packages. The parameter is typed as `dict[str, dict[str, Any]]` (no service imports). The dict structure mirrors `NodeApiMapping` fields: `{"api_spec": "slack.json", "operation_mappings": {"chat:postMessage": "POST /chat.postMessage"}}`.

### 9. Add picofun Dependency to Packager

**Effort: XS**

**File:** `packager/pyproject.toml`

Add `"picofun>=0.1.0"` to the `[project] dependencies` array. The packager uses PicoFun's `Layer` class to prepare the picorun runtime layer and PicoFun's `CdkGenerator` to produce CDK construct code.

### 10. Create PicoFunWriter in Packager

**Effort: M**

**File:** `packager/src/n8n_to_sfn_packager/writers/picofun_writer.py` (new)

Handles PicoFun-specific packaging — the picorun Lambda layer and CDK construct. Uses PicoFun's `Layer(config).prepare()` to create the layer directory with picorun==0.2.1 dependency, and PicoFun's `CdkGenerator.generate()` to produce a CDK construct file.

```python
class PicoFunWriter:
    def write(
        self, picofun_functions: list[LambdaFunctionSpec],
        namespace: str, output_dir: Path,
    ) -> PicoFunOutput:
        """
        1. Layer: PicoFun's Layer(config).prepare() → output_dir/picofun_layer/
        2. CDK: PicoFun's CdkGenerator.generate(lambdas) → output_dir/picofun_construct.py
        Returns metadata for CDK integration.
        """
```

The `PicoFunOutput` dataclass holds the layer directory path and CDK construct file path for consumption by the CDK writer.

### 11. Integrate PicoFunWriter into Packaging Pipeline

**Effort: S**

**File:** `packager/src/n8n_to_sfn_packager/packager.py`

Add a `_step_write_picofun()` method, called after `_step_write_lambdas()` (line 65). The method:

1. Filters `input_data.lambda_functions` for `function_type == LambdaFunctionType.PICOFUN_API_CLIENT` (enum value at `phaeton_models/packager_input.py:28`)
2. If any PicoFun functions exist, invokes `PicoFunWriter.write()`
3. Stores the `PicoFunOutput` for use by the CDK writer
4. If no PicoFun functions, skips silently

Also add `self._picofun_writer = PicoFunWriter()` to `Packager.__init__()` (line 31).

### 12. Modify CDK Writer to Compose PicoFun Construct

**Effort: M**

**File:** `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`

Four changes to the CDK writer:

1. **`_wf_lambda_functions()`** (line 478): Skip functions where `spec.function_type == LambdaFunctionType.PICOFUN_API_CLIENT` — they are handled by PicoFun's CDK construct instead of being generated individually.

2. **`_wf_imports()`** (line 301): When PicoFun Lambdas exist, add an import for the PicoFun construct file: `from construct import PicoFunConstruct` (the file generated by `CdkGenerator`).

3. **New `_wf_picofun_construct()`**: Generate code to instantiate the PicoFun CDK construct in the workflow stack. This construct creates all PicoFun Lambda functions and their shared layer. Wire it to the shared stack's VPC/security group if VPC config is present.

4. **`_wf_lambda_layers()`** (line 426): Reference the PicoFun layer for PicoFun functions.

The `_write_workflow_stack()` method (line 263) needs to accept optional PicoFun metadata and include the new `_wf_picofun_construct()` section in its `sections` list.

---

## P2 — Testing

### 13. Unit Tests for PicoFun Bridge

**Effort: M**

**File:** `n8n-to-sfn/tests/test_picofun_bridge.py` (new)

Test the `PicoFunBridge` class with:
- `test_load_api_spec_openapi3` — parse a minimal OpenAPI 3.0 spec file
- `test_load_api_spec_swagger2` — parse a minimal Swagger 2.0 spec file
- `test_find_endpoint_exact_match` — find endpoint by exact method+path
- `test_find_endpoint_not_found` — returns None for non-existent method+path
- `test_render_endpoint` — produces non-empty formatted Python code containing `picorun` imports
- Use temporary spec files created with `tmp_path` fixture

### 14. Unit Tests for Operation Mapper

**Effort: S**

**File:** `n8n-to-sfn/tests/test_picofun_operation_mapper.py` (new)

Test `resolve_operation_to_endpoint()`:
- `test_exact_resource_operation_match` — `{"resource": "chat", "operation": "postMessage"}` with mapping `{"chat:postMessage": "POST /chat.postMessage"}` → `("POST", "/chat.postMessage")`
- `test_operation_only_match` — when resource is empty, tries operation-only lookup
- `test_case_insensitive_match` — case-insensitive comparison
- `test_returns_none_when_unmapped` — unknown operation returns None
- `test_returns_none_when_mappings_is_none` — None mappings returns None

### 15. Unit Tests for Spec Fetcher

**Effort: S**

**File:** `n8n-to-sfn/tests/test_spec_fetcher.py` (new)

Test `SpecFetcher`:
- Mock boto3 S3 client using `unittest.mock.patch`
- `test_fetch_downloads_from_s3` — verifies S3 `download_file` called with correct bucket/key
- `test_fetch_uses_cache` — second call returns cached file without S3 call
- `test_fetch_handles_s3_error` — raises appropriate error on S3 failure

### 16. Update PicoFunTranslator Tests

**Effort: M**

**File:** `n8n-to-sfn/tests/test_picofun.py`

Existing tests must continue passing (backward compat with placeholder fallback). Add:
- `test_generation_with_valid_spec` — real spec file + operation_mappings → handler code containing `picorun` imports and function definitions
- `test_graceful_degradation_missing_spec` — missing spec file → placeholder code + warning
- `test_graceful_degradation_unmapped_operation` — unknown operation → placeholder code + warning
- `test_graceful_degradation_render_error` — PicoFun render failure → placeholder code + warning
- `test_dependencies_populated` — verify `LambdaArtifact.dependencies` contains `["picorun", "requests", "aws-lambda-powertools"]`
- `test_dependencies_include_boto3_with_credentials` — when credentials present, dependencies include `"boto3"`

### 17. Unit Tests for PicoFunWriter in Packager

**Effort: M**

**File:** `packager/tests/test_picofun_writer.py` (new)

Test the `PicoFunWriter`:
- `test_write_creates_layer_directory` — verify layer directory exists with picorun dependency in pyproject.toml
- `test_write_creates_cdk_construct` — verify CDK construct file is generated
- `test_write_returns_output_metadata` — verify PicoFunOutput contains correct paths
- `test_skip_when_no_picofun_functions` — verify writer is not invoked when no PICOFUN_API_CLIENT functions exist
- Mock PicoFun's `Layer` and `CdkGenerator` to avoid external dependencies in unit tests

### 18. Update Adapter Tests for Spec Mapping Passthrough

**Effort: S**

**File:** `shared/phaeton-models/tests/test_adapter_analyzer_to_translator.py`

Add tests to existing adapter test file:
- `test_convert_with_node_spec_mappings` — verify `convert_report_to_analysis()` with `node_spec_mappings` populates `api_spec` and `operation_mappings` on matching `ClassifiedNode` instances
- `test_convert_without_node_spec_mappings` — backward compat: `None` mappings produces nodes with `api_spec=None` and `operation_mappings=None`
- `test_convert_partial_spec_mappings` — only matching node types get populated, others remain None

### 19. CDK Writer Tests for PicoFun Construct Integration

**Effort: S**

**File:** `packager/tests/test_cdk_writer_picofun.py` (new)

Test the modified CDK writer:
- `test_picofun_functions_excluded_from_lambda_section` — PICOFUN_API_CLIENT functions not in `_wf_lambda_functions()` output
- `test_picofun_import_added` — PicoFun construct import present when PicoFun functions exist
- `test_picofun_construct_section_generated` — `_wf_picofun_construct()` produces valid Python code
- `test_no_picofun_section_when_no_functions` — no PicoFun sections when no PICOFUN_API_CLIENT functions

---

## Recommended Sequencing

The dependency graph is:
- Item 1 (dependency) → Items 3, 4, 5, 6
- Item 2 (TranslationContext field) → Item 7
- Items 3, 4, 5 → Item 6 (translator rewrite uses bridge, mapper, fetcher)
- Item 6 → Item 7 (engine/handler wiring needs the translator)
- Item 8 (adapter) is independent of the translator work
- Item 9 (packager dependency) → Items 10, 11, 12
- Items 10 → 11 → 12
- All implementation items → their respective test items (13-19)
