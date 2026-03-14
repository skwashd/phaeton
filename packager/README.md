# n8n-to-sfn Packager

Generates deployable CDK applications from translated n8n workflows. This is Component 4 in the Phaeton pipeline — it takes the Translation Engine's output and produces a complete, self-contained CDK project with ASL state machine definitions, Lambda functions, IAM policies, SSM credential placeholders, and a migration guide.

## Installation

```bash
uv sync
```

Requires Python >= 3.14.

## Usage

```bash
uv run python -m n8n_to_sfn_packager --input translation_output.json -o output/
```

Options:

- `--input`, `-i`: Path to the PackagerInput JSON file (required)
- `--output`, `-o`: Output directory for the generated package (default: `./output`)
- `--schema`: Path to the ASL JSON Schema file for validation (optional)

## Architecture

```
src/n8n_to_sfn_packager/
  __main__.py          CLI entry point (Typer)
  packager.py          Main orchestrator (Packager class)
  models/
    inputs.py          Input contract (PackagerInput, LambdaFunctionSpec, TriggerConfig, etc.)
    ssm.py             SSM parameter models
  writers/
    asl_writer.py      Validates and writes statemachine/definition.asl.json
    lambda_writer.py   Writes Lambda function directories (handler + dependencies)
    ssm_writer.py      Generates SSM parameter definitions from credentials
    iam_writer.py      Generates least-privilege IAM policies from ASL analysis
    cdk_writer.py      Generates CDK app (app.py, stacks, cdk.json, requirements.txt)
    report_writer.py   Writes MIGRATE.md, conversion reports (JSON + Markdown), README
```

### Packaging pipeline

The `Packager.package()` method runs these steps in order:

1. **Validate ASL** — validate the state machine definition against the ASL JSON Schema
2. **Write ASL** — write `statemachine/definition.asl.json`
3. **Write Lambdas** — write each Lambda function directory with handler code and dependency files
4. **Generate SSM** — generate SSM parameter definitions from credential specs
5. **Generate IAM** — analyze the ASL to produce a least-privilege IAM policy
6. **Write CDK** — generate the CDK application (`app.py`, stacks, `cdk.json`, `requirements.txt`)
7. **Write reports** — generate `MIGRATE.md`, conversion reports (JSON and Markdown), and a README

### Output directory structure

```
output/
├── cdk/
│   ├── app.py                    # CDK app entry point
│   ├── cdk.json                  # CDK configuration
│   ├── requirements.txt          # CDK + construct dependencies
│   └── stacks/
│       ├── workflow_stack.py     # Main stack (state machine, Lambdas, IAM, SSM)
│       └── shared_stack.py       # KMS key, log group, shared resources
├── statemachine/
│   └── definition.asl.json      # ASL state machine definition
├── lambdas/
│   └── <function_name>/         # One directory per Lambda function
│       ├── handler.py|handler.js
│       └── requirements.txt|package.json
├── MIGRATE.md                   # Pre/post-deployment checklist
├── reports/
│   ├── conversion_report.json   # Machine-readable conversion analysis
│   └── conversion_report.md     # Human-readable conversion summary
└── README.md                    # Overview and quickstart
```

### Key models

| Model | Location | Purpose |
|---|---|---|
| `PackagerInput` | `models/inputs.py` | Top-level input contract (from Translation Engine) |
| `LambdaFunctionSpec` | `models/inputs.py` | Lambda function specification (code, runtime, deps) |
| `CredentialSpec` | `models/inputs.py` | SSM parameter placeholder for a credential |
| `OAuthCredentialSpec` | `models/inputs.py` | Extended credential with token rotation config |
| `TriggerSpec` | `models/inputs.py` | Workflow trigger configuration |
| `SubWorkflowReference` | `models/inputs.py` | Reference to a separately-deployed sub-workflow |
| `ConversionReport` | `models/inputs.py` | Conversion feasibility statistics |
| `StateMachineDefinition` | `models/inputs.py` | ASL definition with query language setting |
| `WorkflowMetadata` | `models/inputs.py` | Source workflow and conversion metadata |
| `Packager` | `packager.py` | Main orchestrator class |

## Development

Run tests:

```bash
uv run pytest
```

Run linting and formatting:

```bash
uv run ruff check --fix .
uv run ruff format .
```

Run type checking:

```bash
uv run ty check
```

Run test coverage:

```bash
uv run coverage run -m pytest
uv run coverage report -m
```
