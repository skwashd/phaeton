# n8n-to-sfn Translation Engine

Translation engine that converts analyzed n8n workflows into AWS Step Functions ASL state machine definitions and supporting Lambda artifacts. This is Component 3 in the Phaeton pipeline — it sits between the Workflow Analyzer (which classifies nodes and builds dependency graphs) and the Packager (which generates the deployable CDK application).

## Installation

```bash
uv sync
```

Requires Python >= 3.14.

## Usage

This component is a library with no CLI. It is consumed by the Packager or invoked programmatically:

```python
from n8n_to_sfn.engine import TranslationEngine, TranslationOutput
from n8n_to_sfn.translators.flow_control import FlowControlTranslator
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.triggers import TriggerTranslator
from n8n_to_sfn.translators.code_node import CodeNodeTranslator
from n8n_to_sfn.translators.picofun import PicoFunTranslator

# Build the translator chain
translators = [
    FlowControlTranslator(),
    AWSServiceTranslator(),
    TriggerTranslator(),
    CodeNodeTranslator(),
    PicoFunTranslator(),
]

engine = TranslationEngine(translators=translators, ai_agent=None)

# analysis is a WorkflowAnalysis from the Workflow Analyzer
output: TranslationOutput = engine.translate(analysis)

# output contains:
#   output.state_machine    — ASL StateMachine model
#   output.lambda_artifacts — generated Lambda functions
#   output.trigger_artifacts — trigger infrastructure configs
#   output.conversion_report — translation statistics
#   output.warnings         — any warnings from translation
```

## Architecture

```
src/n8n_to_sfn/
  engine.py            Main orchestrator (TranslationEngine, TranslationOutput)
  validator.py         ASL JSON Schema validation
  items_adapter.py     n8n items-model to Step Functions state adaptation
  errors.py            Error types
  models/
    analysis.py        Input models (ClassifiedNode, WorkflowAnalysis)
    asl.py             ASL state models (StateMachine, TaskState, PassState, etc.)
    n8n.py             n8n workflow JSON models
  translators/
    base.py            BaseTranslator ABC, LambdaArtifact, TriggerArtifact, TranslationResult
    flow_control.py    IF → Choice, Switch → Choice, Merge → Parallel, Wait, NoOp
    aws_service.py     AWS nodes → direct SDK integrations in ASL
    triggers.py        Schedule → EventBridge, Webhook → Lambda fURL, Manual
    code_node.py       JS/Python Code nodes → lift-and-shift Lambda functions
    picofun.py         API nodes → PicoFun-generated Lambda clients
    expressions.py     n8n expression → JSONata translation helpers
    variables.py       Cross-node reference → Step Functions Variable resolution helpers
```

### Key design decisions

- **Plugin-based translators** — Each translator implements `BaseTranslator` with `can_translate()` and `translate()` methods. The engine iterates translators in order until one handles the node.
- **AI agent fallback** — An optional `AIAgentProtocol` implementation handles nodes that no deterministic translator can convert (complex expressions, ambiguous semantics).
- **Topological ordering** — Nodes are processed in dependency order using `graphlib.TopologicalSorter` to ensure upstream states exist before wiring transitions.
- **ASL validation** — Every generated state machine is validated against the ASL JSON Schema via `validator.py`.
- **Typed models** — All ASL states, translation results, and artifacts are Pydantic v2 models.

### Key models

| Model | Location | Purpose |
|---|---|---|
| `TranslationEngine` | `engine.py` | Main orchestrator — accepts `WorkflowAnalysis`, returns `TranslationOutput` |
| `TranslationOutput` | `engine.py` | Final pipeline result (state machine + artifacts + report) |
| `BaseTranslator` | `translators/base.py` | Abstract base for all translator plugins |
| `TranslationResult` | `translators/base.py` | Single-node translation result (states + artifacts) |
| `LambdaArtifact` | `translators/base.py` | Generated Lambda function code and metadata |
| `TriggerArtifact` | `translators/base.py` | Trigger infrastructure configuration |
| `TranslationContext` | `translators/base.py` | Shared context passed to each translator |
| `StateMachine` | `models/asl.py` | ASL state machine definition |
| `ClassifiedNode` | `models/analysis.py` | Input node with classification from the Analyzer |
| `WorkflowAnalysis` | `models/analysis.py` | Full analyzed workflow (nodes, edges, metadata) |

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
