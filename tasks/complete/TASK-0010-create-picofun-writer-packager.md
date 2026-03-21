# Create Picofun Writer Packager

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #10

## Overview

The packager currently has no awareness of PicoFun-specific artifacts. When PicoFun Lambda functions are included in the `PackagerInput`, the packager needs to:

1. Create a **picorun Lambda layer** directory containing the `picorun` runtime dependency (used by all PicoFun-generated handlers)
2. Generate a **CDK construct file** that defines all PicoFun Lambda functions and their shared layer as a reusable CDK construct

PicoFun provides library APIs for both: `Layer(config).prepare()` creates the layer directory with `picorun==0.2.1`, and `CdkGenerator.generate()` produces a CDK construct Python file.

## Dependencies

- **Blocked by:** TASK-0009 (picofun package must be importable in packager)
- **Blocks:** TASK-0011, TASK-0017

## Acceptance Criteria

1. A `PicoFunWriter` class exists in `packager/src/n8n_to_sfn_packager/writers/picofun_writer.py`.
2. A `PicoFunOutput` dataclass exists holding `layer_dir: Path` and `construct_file: Path`.
3. `PicoFunWriter.write()` creates a `picofun_layer/` directory under `output_dir` with picorun dependency.
4. `PicoFunWriter.write()` creates a `picofun_construct.py` file under `output_dir`.
5. `PicoFunWriter.write()` returns a `PicoFunOutput` with correct paths.
6. All public methods and classes have type annotations and docstrings.
7. `uv run pytest` passes in `packager/`.
8. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/picofun_writer.py` (new)

### Technical Approach

1. Create `packager/src/n8n_to_sfn_packager/writers/picofun_writer.py`:

   ```python
   from dataclasses import dataclass
   from pathlib import Path

   from phaeton_models.packager_input import LambdaFunctionSpec
   from picofun.layer import Layer
   from picofun.iac.cdk import CdkGenerator
   from picofun.config import Config

   @dataclass(frozen=True)
   class PicoFunOutput:
       """Metadata from PicoFun artifact generation."""
       layer_dir: Path
       construct_file: Path

   class PicoFunWriter:
       """Generates PicoFun-specific packaging artifacts."""

       def write(
           self,
           picofun_functions: list[LambdaFunctionSpec],
           namespace: str,
           output_dir: Path,
       ) -> PicoFunOutput:
           """Generate picorun layer and CDK construct file."""
   ```

2. In `write()`:
   - Create a `Config` with `output_dir` set to the target directory
   - Call `Layer(config).prepare()` to create `output_dir/picofun_layer/` with picorun dependency
   - Call `CdkGenerator(config).generate(lambdas)` to write `output_dir/picofun_construct.py`
   - Note: `CdkGenerator.generate()` writes to disk and returns nothing (a flagged upstream issue). Read back the generated file path from the config.
   - Return `PicoFunOutput(layer_dir=..., construct_file=...)`

3. The `PicoFunOutput` dataclass is frozen for consistency with project conventions (immutable value objects).

### Testing Requirements

- `packager/tests/test_picofun_writer.py` (new, created in TASK-0017)
- Mock PicoFun's `Layer` and `CdkGenerator` to avoid external dependencies
- Test layer directory creation
- Test CDK construct file generation
- Test returned PicoFunOutput metadata
