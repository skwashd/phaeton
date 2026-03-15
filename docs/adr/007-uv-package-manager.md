# ADR-007: uv as the Python Package Manager and Build Tool

**Status:** Accepted
**Date:** 2025-06-01

## Context

The Phaeton project is a Python monorepo with multiple independent packages that share a common dependency (`phaeton-models`). The build system must support:
- Workspace-level dependency resolution across all packages.
- Editable installs for local development so changes in one package are immediately visible to dependents.
- Per-package lock files for reproducible builds.
- Fast dependency resolution and installation for CI/CD.

Traditional options (pip + pip-tools, Poetry, PDM) were considered, but each had limitations with monorepo workspace support, resolution speed, or editable install handling.

## Decision

Use `uv` as the sole Python package manager, dependency resolver, and build tool across the entire project. Specific configuration:

- **Workspace sources** — each component declares local dependencies via `[tool.uv.sources]` with `{ path = "...", editable = true }` for development.
- **Override dependencies** — the root `pyproject.toml` uses `[tool.uv]` `override-dependencies` to force resolution of `phaeton-models` from the local workspace rather than a registry.
- **Per-component lock files** — each package has its own `uv.lock` alongside a root-level `uv.lock` that ties all components together.
- **Build backends** — `uv_build` is used as the default build backend, with `hatchling` used for specific packages (e.g., `n8n-release-parser`) that need custom build hooks.
- **CLI invocation** — all tools and scripts are run via `uv run <command>` to ensure the correct virtual environment and dependencies are active.

## Consequences

### Positive
- Extremely fast dependency resolution and installation (10-100x faster than pip), significantly improving CI build times.
- Native workspace support handles the monorepo structure without custom scripts or Makefiles.
- Editable installs work reliably across the workspace, so changes to `phaeton-models` are immediately available to all dependent components.
- `uv.lock` files provide fully reproducible builds with exact version pinning.
- Single tool replaces pip, pip-tools, virtualenv, and most of the build toolchain.

### Negative
- `uv` is a relatively new tool with a smaller user base than pip or Poetry, which may create onboarding friction for contributors unfamiliar with it.
- The `phaeton-models` leaf dependency constraint must be carefully managed — circular workspace dependencies cause resolution failures in uv.
- Some advanced pip features (e.g., certain editable install modes, custom index authentication) may not yet be supported.

### Neutral
- Python version requirement is 3.14+ for most components, which aligns with uv's focus on modern Python versions.
- The `uv_build` backend is used for most packages but is not required — packages can use any PEP 517-compatible backend.
- Developers need `uv` installed locally but do not need to manage virtual environments manually — `uv run` handles this automatically.
