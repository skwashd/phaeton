# phaeton-models

See the [top-level CLAUDE.md](../../CLAUDE.md) for repo-wide commands, linting rules, and conventions.

## Critical Rules

- **NEVER add other services (n8n-to-sfn, packager, workflow-analyzer, etc.) as dependencies of this package** -- not even as dev dependencies. This is a shared library that other services depend on. Adding a service as a dependency creates a circular dependency that breaks resolution. Only `pydantic` and standard-library packages are allowed as dependencies.
- Adapters in this package must only import from `phaeton_models.*` submodules, never from service packages. If an adapter needs types from two services, those types must be defined as boundary models within `phaeton_models` first.
