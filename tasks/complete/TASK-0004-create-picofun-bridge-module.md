# Create Picofun Bridge Module

**Priority:** P0
**Effort:** M
**Gap Analysis Ref:** Item #4

## Overview

The PicoFun library has several entry points (`Spec.to_api_spec()`, `LambdaGenerator.render()`, parser plugin system) that need to be called from the `PicoFunTranslator`. Rather than scattering PicoFun API calls throughout the translator, a bridge module wraps all PicoFun interactions behind a clean internal interface.

The bridge uses PicoFun's IR models (`ApiSpec`, `Endpoint`) and the parser plugin system (`get_parser()` / `discover_parsers()`) which auto-detects Swagger 2.0 vs OpenAPI 3.x format. The `LambdaGenerator.render(base_url, endpoint)` method takes an `Endpoint` object (not raw dicts) and returns rendered Python handler code as a string.

Key design decisions:
- `Config(auth_enabled=False)` since Phaeton manages auth via SSM/CredentialArtifacts
- Template path resolved via `importlib.resources.files("picofun")` (same pattern as PicoFun CLI line 134)
- The bridge is stateless per-call; `spec_directory` is set at construction time

## Dependencies

- **Blocked by:** TASK-0001 (picofun package must be importable)
- **Blocks:** TASK-0006, TASK-0013

## Acceptance Criteria

1. A `PicoFunBridge` class exists in `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_bridge.py`.
2. `load_api_spec(spec_filename)` parses a spec file from `spec_directory` and returns a PicoFun `ApiSpec` object.
3. `load_api_spec` auto-detects Swagger 2.0 and OpenAPI 3.x formats via PicoFun's parser plugin system.
4. `find_endpoint(api_spec, method, path)` returns the matching `Endpoint` or `None`.
5. `render_endpoint(base_url, endpoint, namespace)` returns non-empty Python handler code containing `picorun` imports.
6. All public methods and the class have type annotations and docstrings.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_bridge.py` (new)

### Technical Approach

1. Create `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_bridge.py` with:

   ```python
   from picofun.spec import Spec
   from picofun.lambda_generator import LambdaGenerator
   from picofun.config import Config
   from picofun.models import ApiSpec, Endpoint

   class PicoFunBridge:
       def __init__(self, spec_directory: str = "") -> None:
           """Initialize bridge with path to local spec file directory."""

       def load_api_spec(self, spec_filename: str, format_override: str | None = None) -> ApiSpec:
           """Parse spec file → PicoFun ApiSpec IR via Spec.to_api_spec()."""

       def find_endpoint(self, api_spec: ApiSpec, method: str, path: str) -> Endpoint | None:
           """Find matching Endpoint in the ApiSpec by method+path."""

       def render_endpoint(self, base_url: str, endpoint: Endpoint, namespace: str) -> str:
           """Render a single endpoint handler using LambdaGenerator.render(base_url, endpoint)."""
   ```

2. `load_api_spec()`:
   - Construct the full path: `Path(self._spec_directory) / spec_filename`
   - Call `Spec(spec_path).to_api_spec()` which auto-detects format via parser plugins
   - Return the `ApiSpec` IR object

3. `find_endpoint()`:
   - Iterate through `api_spec.endpoints`
   - Match on `endpoint.method.upper() == method.upper()` and `endpoint.path == path`
   - Return `None` if no match found

4. `render_endpoint()`:
   - Create a `Config(auth_enabled=False, output_dir="/tmp")` (output_dir required by Config but unused for render-only)
   - Instantiate `LambdaGenerator(config)` with the template path from `importlib.resources.files("picofun")`
   - Call `generator.render(base_url, endpoint)` which returns the handler code as a string

### Testing Requirements

- `n8n-to-sfn/tests/test_picofun_bridge.py` (new, created in TASK-0013)
- Test with minimal OpenAPI 3.0 and Swagger 2.0 spec files
- Test endpoint matching (exact match and not-found)
- Test render produces valid Python with `picorun` imports
