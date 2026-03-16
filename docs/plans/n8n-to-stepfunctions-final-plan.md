# n8n to AWS Step Functions Converter — Architecture Plan

## Project Overview

A modular platform that converts n8n workflows to AWS Step Functions, using deterministic translation wherever possible and an AI agent as a fallback for complex cases. The system leverages PicoFun for API client Lambda generation, JSONata for data transformation, and CDK for deployment packaging.

**Target**: Enterprise customers migrating from n8n to production-grade AWS-native orchestration.
**Initial delivery**: Internal tool with human review (mechanical turking). End goal: fully automated SaaS.

---

## Scope Boundaries (Initial Version)

**In scope:**
- n8n stable releases from the previous 12 months
- Standard Step Functions workflows only (no Express)
- Third-party SaaS API nodes (via PicoFun-generated Lambdas)
- AWS service nodes (native SDK integrations in ASL)
- Flow control nodes (IF, Switch, Merge, SplitInBatches, loops)
- Code nodes (JS and Python — lift-and-shift to Lambda)
- JSONata for all data transformations
- SSM Parameter Store for all credentials
- CDK for deployment packaging
- ASL defined in JSON only
- Priority nodes: core flow control, HTTP Request, AWS services, and top 50 by popularity from n8n's integrations endpoint
- Sub-workflows as separate Step Functions invoked via `states:StartExecution`

**Out of scope:**
- Google Cloud / Azure service nodes
- Binary data and filesystem nodes
- Express workflows
- Idempotency guarantees
- End-user testing tooling (documentation only)
- End-user deployment strategy (recommendations only)
- Community nodes (n8n-nodes-base only)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     n8n Workflow JSON                        │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Component 1: n8n Release Parser                            │
│  - Extracts node type registry from n8n-nodes-base          │
│  - Diffs against previous releases                          │
│  - Maps new/changed nodes to API specs                      │
│  - Maintains versioned node catalogue (12-month window)     │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Component 2: Workflow Analyzer & Node Mapper                │
│  - Parses workflow JSON                                      │
│  - Classifies each node (AWS-native / PicoFun / unsupported)│
│  - Builds dependency graph (data flow + cross-node refs)     │
│  - Identifies required PicoFun clients                       │
│  - Classifies expressions (JSONata / Variable / Lambda)      │
│  - Detects potential payload size issues                     │
│  - Generates conversion confidence report                    │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Component 3: Translation Engine                             │
│  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │ Deterministic Mapper │  │ AI Agent (fallback)         │  │
│  │ - Flow control → ASL │  │ - Complex expression logic  │  │
│  │ - AWS nodes → SDK    │  │ - Ambiguous node semantics  │  │
│  │ - Expressions→JSONata│  │ - Edge case handling        │  │
│  │ - Merges → JSONata   │  │                             │  │
│  │ - Triggers → Events  │  │                             │  │
│  └──────────────────────┘  └─────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ PicoFun Integration Layer                            │   │
│  │ - Generates Lambda clients from API specs            │   │
│  │ - ~290 indexed API spec files (Swagger + OpenAPI v3) │   │
│  │ - GraphQL client generation (separate project)       │   │
│  │ - SSM Parameter Store for credentials                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Component 4: Packager                                       │
│  - CDK app with all constructs                               │
│  - ASL state machine definition (JSON)                       │
│  - PicoFun-generated Lambda functions                        │
│  - Lift-and-shift Lambdas for Code nodes                     │
│  - Lambda fURL configuration (webhook + callback triggers)   │
│  - SSM parameters with descriptive placeholders              │
│  - KMS key for encryption (workflow, creds, logs)            │
│  - CloudWatch Log Groups + X-Ray tracing                     │
│  - IAM roles (least-privilege)                               │
│  - EventBridge rules for scheduled triggers + OAuth rotation │
│  - MIGRATE.md with user action items                         │
│  - Conversion report                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Component 1: n8n Release Parser

### Purpose
Maintain a versioned catalogue of all n8n node types, their parameters, credentials, and API mappings. Detect new or changed nodes across releases and map them to available API specs for PicoFun client generation.

### Design

**Input**: n8n release tags (npm `n8n-nodes-base` package)
**Output**: Versioned node catalogue stored as structured data

**Process:**
1. For each n8n stable release within the 12-month window, pull the `n8n-nodes-base` package.
2. Parse every node's `INodeTypeDescription` to extract: node type name, version, parameters schema, credential types, resource/operation pairs, input/output count.
3. Diff against the previous release to identify: new nodes, removed nodes, changed parameter schemas, new operations on existing nodes.
4. For new/changed nodes, attempt to match against the indexed API spec library (~290 specs) using the node's base URL patterns, credential type hints, and resource names.
5. Flag unmatched nodes for manual review and spec acquisition.

### Node Version Handling

n8n nodes are versioned with `typeVersion`. Workflows pin to their creation-time version. The catalogue must store all versions of each node within the 12-month window. When converting a workflow, the system uses the `typeVersion` from each node in the workflow JSON to select the correct catalogue entry.

### API Spec Matching Strategy

The ~290 API spec files need an index that maps each spec to: the service name, base URL(s), authentication type, and a list of resource/operation pairs. When a new n8n node appears, the matcher should:

1. Extract the base URL from the node's credential type or `requestDefaults`.
2. Fuzzy-match against the spec index by URL.
3. If no URL match, try matching by service name (e.g., n8n node `Slack` → `slack-web-api-v2.json`).
4. For matched specs, verify that the node's operations map to spec endpoints.
5. Generate a mapping file linking n8n node operations to spec endpoint paths.

**Output format for each node:**
```json
{
  "nodeType": "n8n-nodes-base.slack",
  "typeVersion": 2,
  "apiSpec": "slack-web-api-v2.json",
  "specFormat": "openapi3",
  "operationMappings": {
    "message:send": "POST /chat.postMessage",
    "channel:getAll": "GET /conversations.list"
  },
  "credentialType": "slackApi",
  "authType": "oauth2",
  "unmappedOperations": ["message:getPermalink"],
  "specCoverage": 0.92
}
```

### Priority Node Selection

The initial translation registry targets three groups:

1. **Core flow control and utility nodes**: IF, Switch, Merge, SplitInBatches, Set, Code, Function, NoOp, Wait, HTTP Request, Webhook, Schedule Trigger, Manual Trigger, Execute Workflow, Respond to Webhook, Error Trigger.
2. **AWS service nodes**: S3, DynamoDB, SQS, SNS, SES, Lambda, EventBridge, Secrets Manager, Textract, Comprehend, Rekognition, Step Functions, CloudWatch, Kinesis.
3. **Top 50 by popularity**: Sourced from n8n's integrations endpoint (sorted by popularity). Based on the current ranking, this includes: code, manualTrigger, httpRequest, set, if, webhook, scheduleTrigger, noOp, merge, splitInBatches, switch, formTrigger, wait, respondToWebhook, dataTable, splitOut, filter, extractFromFile, aggregate, readWriteFile, executeWorkflow, supabase, convertToFile, executeWorkflowTrigger, airtable, httpRequestTool, whatsApp, whatsAppTrigger, emailSend, limit, slack, rssFeedRead, html, form, discord, emailReadImap, youTube, executeCommand, dateTime, summarize, executionData, errorTrigger, stopAndError, facebookGraphApi, aiTransform, removeDuplicates, slackTrigger, markdown, supabaseTool, and rssFeedReadTrigger.

**Note**: Google/GCP/Microsoft/Azure services are out of scope for the initial implementation.

---

## Component 2: Workflow Analyzer & Node Mapper

### Purpose
Parse an uploaded n8n workflow JSON, classify every node, build a complete dependency graph, identify cross-node data references, and produce an analysis report that drives the translation engine.

### Design

**Input**: n8n workflow JSON export
**Output**: Annotated workflow graph + conversion feasibility report

### Step 1: Workflow JSON Parsing

n8n workflow JSON contains: `nodes` (array of node definitions), `connections` (adjacency map from node outputs to node inputs), `settings` (execution order, timezone, etc.), and `pinData` (optional test data).

Each node has: `type` (e.g., `n8n-nodes-base.slack`), `typeVersion`, `position`, `parameters` (operation-specific config including expressions), `credentials` (credential references), and `id`.

Connections encode the DAG: `{ "NodeName": { "main": [[{ "node": "NextNode", "type": "main", "index": 0 }]] } }`. The `main` key contains output indices, each mapping to an array of downstream connections.

### Step 2: Node Classification

Every node gets classified into one of these categories:

| Category | Translation Strategy | Examples |
|---|---|---|
| **AWS Native** | Direct SDK integration in ASL | S3, DynamoDB, SQS, SNS, SES, Lambda, EventBridge |
| **Flow Control** | Deterministic ASL mapping | IF, Switch, Merge, SplitInBatches, NoOp, Wait |
| **Trigger** | EventBridge rule / Lambda fURL / manual | Webhook, Schedule, Manual, app-specific triggers |
| **PicoFun API** | Generate Lambda from API spec | Any node with a matched API spec (~290 specs) |
| **GraphQL API** | Generate Lambda from GraphQL schema | Nodes targeting GraphQL endpoints |
| **Code (JS)** | Lift-and-shift to Node.js Lambda | Code node (JavaScript mode) |
| **Code (Python)** | Lift-and-shift to Python Lambda | Code node (Python mode) |
| **Unsupported** | Flagged in report | Binary nodes, filesystem nodes, unknown nodes |

### Step 3: Dependency Graph Construction

Build a directed acyclic graph (DAG) from the connections map. Additionally, scan all expression strings in every node's parameters for cross-node references (`$('NodeName')`, `$node["NodeName"]`) and add data-dependency edges that don't appear in the explicit connections.

This graph is critical for:
- Determining execution order for sequential states
- Identifying where Parallel states are needed (multiple outputs from one node)
- Detecting cross-node references that require Step Functions Variables
- Finding merge points that need special handling

### Step 4: Expression Classification

For every expression in every node parameter, classify it:

**Category A — Direct JSONata translation (~40-50% of expressions):**
- Simple field access: `{{ $json.email }}` → `{% $states.input.email %}`
- Basic string ops: `{{ $json.name.toUpperCase() }}` → `{% $uppercase($states.input.name) %}`
- Math: `{{ $json.price * 1.1 }}` → `{% $states.input.price * 1.1 %}`
- Ternary: `{{ $json.active ? "yes" : "no" }}` → `{% $states.input.active ? "yes" : "no" %}`
- Template literals: `` {{ `Hello ${$json.name}` }} `` → `{% "Hello " & $states.input.name %}`

**Category B — Requires Variables (~20-30%):**
- Cross-node references: `{{ $('Lookup').first().json.id }}` → `{% $lookupResult.id %}`
  - Requires injecting an `Assign` block in the referenced state's output
- Execution metadata: `{{ $execution.id }}` → `{% $states.context.Execution.Id %}`

**Category C — Requires Lambda extraction (~20-30%):**
- Complex JS: IIFEs, closures, `Array.prototype` methods beyond simple map/filter
- Luxon date manipulation: `{{ $now.plus({days: 5}).toFormat('yyyy-MM-dd') }}`
- JMESPath queries: `{{ $jmespath($json, 'users[?age > `30`].name') }}`
- `$env` access, `require()`, multi-statement expressions

**Implementation approach**: Use a JavaScript AST parser (e.g., `acorn` via a Node.js subprocess from Python, or a Python-native JS parser) to analyze each expression. Walk the AST to determine:
- Does it only use property access, arithmetic, string concat, and ternary? → Category A
- Does it reference other nodes? → Category B
- Everything else → Category C

### Step 5: Payload Size Analysis

Estimate whether any state's output might exceed the current payload limit. Heuristics:
- Nodes that fetch lists (getAll operations) with no explicit limit → flag as warning
- Map states processing large arrays → flag as warning
- Multiple merge operations accumulating data → flag as warning

**Design note**: The system should treat the payload limit as a configurable value (currently 256 KiB, anticipated to increase to 1 MiB). Generate warnings in the conversion report with recommendations but do not block conversion. The limit is a known constraint documented in MIGRATE.md.

### Step 6: Conversion Feasibility Report

Generate a report for the human reviewer containing:
- Total nodes and classification breakdown
- Expression classification breakdown with examples
- Unsupported nodes (blocking issues)
- Payload size warnings
- Cross-node reference map (which Variables are needed)
- Estimated PicoFun clients to generate
- Confidence score (percentage of deterministic vs. AI-assisted translation)
- Missing API specs that need to be acquired
- Sub-workflows detected (listed for separate conversion)

---

## Component 3: Translation Engine

### Purpose
Convert the analyzed workflow into ASL JSON + supporting Lambda functions, using deterministic translation for everything possible and the AI agent only for what can't be mapped mechanically.

### Deterministic Translation Rules

#### Flow Control Mapping

**IF Node → Choice State:**
```json
{
  "Type": "Choice",
  "Choices": [
    {
      "Next": "TrueBranch",
      "Condition": "{% $states.input.amount > 100 %}"
    }
  ],
  "Default": "FalseBranch"
}
```

**Switch Node → Choice State (multiple rules):**
Maps each case to a Choice rule. The "fallback" output maps to `Default`.

**SplitInBatches → Map State:**
```json
{
  "Type": "Map",
  "ItemsPath": "{% $states.input.items %}",
  "MaxConcurrency": 1,
  "ItemProcessor": {
    "ProcessorConfig": { "Mode": "INLINE" },
    "StartAt": "ProcessItem",
    "States": { "..." : "..." }
  }
}
```
`MaxConcurrency: 1` preserves n8n's sequential batch processing semantics. Can be increased if the workflow doesn't depend on sequential execution.

**Merge Node (Append) → Parallel State + JSONata Pass:**
```json
{
  "Type": "Pass",
  "Output": "{% $states.input[0] ~> $append($states.input[1]) %}"
}
```

**Merge Node (Merge by Key) → Parallel State + JSONata Pass:**
```json
{
  "Type": "Pass",
  "Output": "{% $map($states.input[0], function($left) { $merge([$left, ($filter($states.input[1], function($right) { $right.id = $left.id }))[0]]) }) %}"
}
```
This performs a left join on a key field entirely in JSONata. The key field name is extracted from the n8n Merge node's `mergeByFields` parameter. For complex multi-key joins or outer joins, the AI agent generates a more complex JSONata expression or falls back to a Lambda.

**Merge Node (Merge by Index) → Parallel State + JSONata Pass:**
```json
{
  "Type": "Pass",
  "Output": "{% $map($states.input[0], function($v, $i) { $merge([$v, $states.input[1][$i]]) }) %}"
}
```

**Wait Node → Wait State:**
Direct mapping. Supports `Seconds`, `Timestamp`, `SecondsPath`, `TimestampPath`.

**NoOp → Pass State:**
Direct mapping.

**Execute Workflow → Nested Step Function Execution:**
```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::states:startExecution.sync:2",
  "Parameters": {
    "StateMachineArn": "${SubWorkflowArn}",
    "Input": "{% $states.input %}"
  }
}
```
Sub-workflows are converted as separate Step Functions. The parent references them by ARN. The CDK stack accepts sub-workflow ARNs as parameters, and MIGRATE.md documents which sub-workflows need to be converted and deployed first.

#### AWS Service Node Mapping

n8n AWS nodes translate to direct SDK integrations in ASL, bypassing Lambda entirely:

| n8n Node | ASL Resource Pattern |
|---|---|
| AWS S3 | `arn:aws:states:::aws-sdk:s3:putObject` / `getObject` / etc. |
| AWS DynamoDB | `arn:aws:states:::aws-sdk:dynamodb:putItem` / `query` / etc. |
| AWS SQS | `arn:aws:states:::aws-sdk:sqs:sendMessage` |
| AWS SNS | `arn:aws:states:::aws-sdk:sns:publish` |
| AWS SES | `arn:aws:states:::aws-sdk:ses:sendEmail` |
| AWS Lambda | `arn:aws:states:::lambda:invoke` |
| AWS EventBridge | `arn:aws:states:::aws-sdk:eventbridge:putEvents` |

Parameters from the n8n node configuration map to the SDK call's `Parameters` block. The translator converts n8n's camelCase parameter names to the AWS SDK's PascalCase format.

#### Trigger Mapping

| n8n Trigger | AWS Equivalent |
|---|---|
| Schedule Trigger | EventBridge Scheduler rule targeting the state machine |
| Webhook | Lambda with function URL that calls `StartExecution` |
| Manual Trigger | Direct `StartExecution` via AWS Console / CLI / SDK |
| App-specific trigger (e.g., Slack event) | Lambda fURL receiving the event + `StartExecution` |

For webhook triggers: the Lambda fURL handler parses the incoming request, extracts the relevant payload, and passes it as input to `StartExecution`. The handler returns the appropriate response (e.g., Slack challenge verification, webhook acknowledgment).

#### Callback / Wait-for-Webhook Pattern

n8n's `$execution.resumeUrl` and wait-for-webhook patterns map to Step Functions' `.waitForTaskToken` integration pattern:

1. The state that needs to wait uses `.waitForTaskToken` and passes the task token to the external system.
2. A Lambda with a function URL receives the callback from the external system.
3. The fURL Lambda calls `SendTaskSuccess` (or `SendTaskFailure`) with the task token and callback payload.
4. The state machine resumes execution with the callback data.

The converter generates the fURL Lambda and wires it into the CDK stack. The callback URL (the fURL endpoint) is documented in MIGRATE.md for the user to configure in the external system.

#### Code Node Handling — Lift and Shift

Code nodes (both JavaScript and Python) are extracted verbatim into Lambda functions:

**JavaScript Code nodes:**
- Runtime: Node.js (latest LTS)
- The node's code is wrapped in a Lambda handler that receives the items array as input and returns the modified items array
- Dependencies detected from `require()` calls are added to `package.json`
- Luxon is included by default (n8n bundles it)

**Python Code nodes:**
- Runtime: Python (latest supported)
- The node's code is wrapped in a Lambda handler
- Dependencies are added to `requirements.txt`

**Handler wrapper template (JS):**
```javascript
// Auto-generated wrapper for n8n Code node: {nodeName}
const handler = async (event) => {
  const items = event.items || [event];
  // --- Begin n8n Code node content ---
  {originalCode}
  // --- End n8n Code node content ---
  return { items: result };
};
exports.handler = handler;
```

The wrapper adapts the n8n items-array contract to Lambda's event/response contract. The human reviewer should validate that the code doesn't rely on n8n-specific globals beyond `$input`, `$json`, and `$items`.

#### Expression Translation (Category A → JSONata)

Translation table mapping n8n expression patterns to JSONata equivalents:

| n8n Expression | JSONata Equivalent |
|---|---|
| `$json.field` | `$states.input.field` |
| `$json.field.subfield` | `$states.input.field.subfield` |
| `$json.arr[0]` | `$states.input.arr[0]` |
| `$json.name.toUpperCase()` | `$uppercase($states.input.name)` |
| `$json.name.toLowerCase()` | `$lowercase($states.input.name)` |
| `$json.text.trim()` | `$trim($states.input.text)` |
| `$json.text.split(',')` | `$split($states.input.text, ',')` |
| `$json.text.replace('a','b')` | `$replace($states.input.text, 'a', 'b')` |
| `$json.text.includes('x')` | `$contains($states.input.text, 'x')` |
| `$json.text.length` | `$length($states.input.text)` |
| `$json.arr.length` | `$count($states.input.arr)` |
| `$json.a + $json.b` | `$states.input.a + $states.input.b` |
| `$json.a > 10 ? 'high' : 'low'` | `$states.input.a > 10 ? 'high' : 'low'` |
| `Math.round($json.val)` | `$round($states.input.val)` |
| `Math.floor($json.val)` | `$floor($states.input.val)` |
| `Math.ceil($json.val)` | `$ceil($states.input.val)` |
| `Object.keys($json)` | `$keys($states.input)` |
| `JSON.stringify($json)` | `$string($states.input)` |
| `parseInt($json.str)` | `$number($states.input.str)` |
| `` `Hello ${$json.name}` `` | `"Hello " & $states.input.name` |
| `$json.items.map(i => i.name)` | `$states.input.items.name` (JSONata implicit map) |
| `$json.items.filter(i => i.active)` | `$states.input.items[active = true]` |
| `new Date().toISOString()` | `$now()` |
| `$json.arr.sort((a,b) => a.n - b.n)` | `$sort($states.input.arr, function($a,$b){ $a.n > $b.n })` |
| `$json.arr.reduce((s,i) => s+i.v, 0)` | `$sum($states.input.arr.v)` |
| `[...$json.a, ...$json.b]` | `$append($states.input.a, $states.input.b)` |
| `{...$json.a, ...$json.b}` | `$merge([$states.input.a, $states.input.b])` |

#### Cross-Node References (Category B → Variables)

When the analyzer detects a cross-node reference like `$('Lookup').first().json.id`, the translator:

1. Adds an `Assign` block to the referenced state's output definition:
```json
{
  "Type": "Task",
  "Comment": "Lookup",
  "Assign": {
    "lookupResult": "{% $states.result %}"
  }
}
```

2. Replaces the expression in the consuming state:
```
$('Lookup').first().json.id  →  {% $lookupResult.id %}
```

Variable naming convention: `camelCase(nodeName) + "Result"`. Collisions resolved by appending numeric suffix.

### AI Agent Integration

The AI agent handles Category C expressions and any node translation the deterministic mapper can't resolve.

**Input to the agent:**
- The original n8n node configuration (full JSON)
- The node's type description (parameters, operations)
- The classified expression(s) that need translation
- The surrounding workflow context (upstream/downstream nodes)
- The target state type and position in the ASL

**Expected output from the agent:**
- For expressions: a JSONata expression or a Lambda function body
- For full nodes: a complete ASL state definition + any supporting Lambda code
- Confidence score (high / medium / low) for the human reviewer

**Agent constraints:**
- Must produce valid ASL JSON
- Must use JSONata (not JSONPath) for all data access
- Must use SSM Parameter Store for any credentials
- Must flag if it's uncertain about semantic equivalence

The agent is called per-node (not per-workflow) to keep context focused and outputs reviewable. Each agent output is tagged with metadata linking it back to the source node for traceability.

### n8n Items Model → Step Functions State Adaptation

**Pattern 1: Single-item flow (no wrapping needed)**

When a workflow processes one item at a time (e.g., webhook receives one event → process it → send notification), the n8n items model collapses to a single JSON object. Each n8n node becomes an ASL state, and `$json.field` maps directly to `$states.input.field`.

**Pattern 2: List processing (Map state wrapping)**

When a node produces a list (e.g., "Get All Contacts"), the downstream chain operates on each item:
1. Detect the list-producing node by operation type (getAll, search, list).
2. Wrap the downstream chain (up to the next merge or termination) in a Map state.
3. Inside the Map state, each item is processed as a single JSON object.
4. The Map state's output is the collected array of results.

**Pattern 3: Multi-branch merge**

When two branches converge at a Merge node, use a Parallel state to execute both branches, then apply the merge logic via JSONata in a Pass state. The Parallel state's output is an array of branch results: `$states.input[0]` is branch 0's output, `$states.input[1]` is branch 1's output.

**Pattern 4: Accumulation across nodes**

When a workflow accumulates data across multiple nodes (e.g., enriching items with data from multiple sources), use Variables to carry forward intermediate results. Each enrichment step assigns its result to a Variable, and the final state combines them via JSONata.

### Error Handling

States without explicit error handling in the n8n workflow are left without Retry or Catch blocks in ASL. If they fail, the Step Function execution fails.

Step Functions emit `Step Functions Execution Status Change` events to EventBridge for all status transitions including failures. The user can configure EventBridge rules to capture `FAILED`, `TIMED_OUT`, and `ABORTED` events and route them to SNS, Lambda, or other targets. This is documented in MIGRATE.md as a recommended post-deployment configuration.

n8n nodes with explicit error handling translate as follows:
- `continueOnFail: true` → `Catch` block that routes to the next state
- `retryOnFail: true` with `maxTries` and `waitBetweenTries` → `Retry` block with matching `MaxAttempts` and `IntervalSeconds`

---

## Component 4: Packager

### Purpose
Generate a deployable CDK application containing all artifacts needed to run the converted workflow on AWS.

### Output Structure

```
output/
├── cdk/
│   ├── app.py                          # CDK app entry point
│   ├── cdk.json                        # CDK configuration
│   ├── requirements.txt                # CDK + construct dependencies
│   └── stacks/
│       ├── workflow_stack.py            # Main stack
│       └── shared_stack.py             # KMS key, log group, shared resources
├── statemachine/
│   └── definition.asl.json             # ASL state machine definition (JSON)
├── lambdas/
│   ├── webhook_handler/                # Lambda fURL for webhook triggers
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── callback_handler/               # Lambda fURL for waitForTaskToken callbacks
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── slack_api/                      # PicoFun-generated client (example)
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── code_node_process_data/         # Lift-and-shift JS Code node (example)
│   │   ├── handler.js
│   │   └── package.json
│   └── oauth_refresh/                  # OAuth token rotation handler
│       ├── handler.py
│       └── requirements.txt
├── MIGRATE.md                          # User action items and manual steps
├── reports/
│   ├── conversion_report.json          # Machine-readable conversion analysis
│   └── conversion_report.md            # Human-readable conversion summary
└── README.md                           # Overview and quickstart
```

### CDK Stack Contents

**Shared Stack (`shared_stack.py`):**
- KMS key for encrypting: state machine data at rest, SSM SecureString parameters, CloudWatch log groups
- CloudWatch Log Group for Step Functions execution logs (encrypted with KMS key, `includeExecutionData: true`)
- X-Ray tracing group

**Workflow Stack (`workflow_stack.py`):**
- `aws_stepfunctions.StateMachine` — Standard workflow type, referencing `definition.asl.json`, KMS encryption, CloudWatch logging, X-Ray tracing enabled
- `aws_lambda.Function` for each PicoFun-generated API client — Python runtime, bundled with dependencies
- `aws_lambda.Function` for each lift-and-shift Code node — Node.js or Python runtime as appropriate
- `aws_lambda.FunctionUrl` for webhook trigger Lambdas and callback handler Lambdas
- `aws_ssm.StringParameter` (SecureString) for each credential — created with descriptive placeholder values (e.g., `<your-slack-oauth-token>`, `<your-salesforce-client-secret>`)
- `aws_events.Rule` for schedule triggers — EventBridge Scheduler targeting the state machine
- `aws_events.Rule` + `aws_lambda.Function` for OAuth token rotation — EventBridge scheduled event triggering a rotation Lambda
- `aws_iam.Role` for the state machine — least-privilege (see IAM Policy Generation)
- CDK parameters for sub-workflow ARNs (injected into ASL via CDK substitutions)

### IAM Policy Generation

The packager generates a least-privilege execution role by analyzing the ASL definition:
- For each `lambda:invoke` Task: `lambda:InvokeFunction` on the specific function ARN
- For each `aws-sdk:*` Task: the specific SDK action (e.g., `s3:PutObject`) on the specific resource ARN
- SSM reads: `ssm:GetParameter` + `ssm:GetParametersByPath` on the specific parameter paths
- KMS: `kms:Decrypt` on the specific KMS key ARN
- Logging: `logs:CreateLogDelivery`, `logs:GetLogDelivery`, `logs:UpdateLogDelivery`, `logs:PutLogEvents` on the specific log group
- X-Ray: `xray:PutTraceSegments`, `xray:PutTelemetryRecords`
- Sub-workflows: `states:StartExecution` on the specific sub-workflow ARNs

### OAuth Token Rotation

For nodes using OAuth2 (once PicoFun adds support):
- Refresh token stored in SSM Parameter Store (SecureString, encrypted with KMS key)
- EventBridge Scheduler triggers a rotation Lambda on a configurable schedule (e.g., every 50 minutes for 60-minute token expiry)
- Rotation Lambda: reads refresh token from SSM → calls OAuth2 token endpoint → writes new access token + new refresh token back to SSM
- PicoFun-generated Lambdas read the access token from SSM at invocation time
- Rotation schedule is per-credential, configured in the CDK stack

### MIGRATE.md Generation

The MIGRATE.md file is a structured checklist of all manual actions the user must take before and after deployment. Generated dynamically based on the conversion:

**Pre-deployment:**
- [ ] Populate SSM parameters with real credential values (table listing every parameter path and what it expects)
- [ ] Convert and deploy sub-workflows first (list of sub-workflow names and their n8n source files)
- [ ] Update sub-workflow ARN parameters in CDK context or `cdk.json`
- [ ] Review AI-translated nodes flagged as medium/low confidence (list with links to conversion report)
- [ ] Review payload size warnings (list of states with potential issues)

**Deployment:**
- [ ] Install CDK dependencies: `pip install -r requirements.txt`
- [ ] Bootstrap CDK (if not already done): `cdk bootstrap`
- [ ] Deploy: `cdk deploy`

**Post-deployment:**
- [ ] Configure webhook URLs in external systems (list of fURL endpoints and where they should be registered)
- [ ] Configure EventBridge rules for failure notifications (recommended SNS topic + email subscription)
- [ ] Verify scheduled triggers are firing correctly
- [ ] Run a test execution via AWS Console with sample input
- [ ] Review CloudWatch logs and X-Ray traces for the test execution

---

## Rate Limiting and Concurrency Control

n8n runs on a single server with natural serialization. Step Functions Map states can blast external APIs with concurrent requests.

**Strategy:**
- Default `MaxConcurrency: 5` on all Map states calling external APIs (configurable per node via the translation registry)
- For APIs with known rate limits (extractable from API specs `x-rateLimit-*` extensions or hardcoded in the registry), set `MaxConcurrency` accordingly
- Add Retry with exponential backoff on all external API Task states:
```json
"Retry": [
  {
    "ErrorEquals": ["States.TaskFailed"],
    "IntervalSeconds": 2,
    "MaxAttempts": 3,
    "BackoffRate": 2.0,
    "MaxDelaySeconds": 30
  }
]
```
- Document recommended concurrency settings per API in the conversion report

---

## Observability

### CloudWatch Logging
- All execution events logged to a dedicated CloudWatch Log Group
- Log group encrypted with the shared KMS key
- `includeExecutionData: true` for full state input/output logging
- MIGRATE.md warns about cost and data sensitivity implications of full execution logging

### X-Ray Tracing
- Enabled on the state machine
- Each Lambda function instrumented with X-Ray SDK (added to Lambda dependencies automatically)
- Provides end-to-end trace view comparable to n8n's execution history

### CloudWatch Dashboard (generated)
- Execution count / success / failure metrics
- P50 / P90 / P99 execution duration
- Lambda error rates per function
- State transition counts

---

## Versioning Strategy

### n8n Release Tracking
- Support any stable n8n release from the previous 12 months
- The node catalogue is versioned: each entry records which n8n versions it applies to
- When converting a workflow, the system detects the source n8n version from the workflow JSON metadata or accepts it as user input
- The translator uses the matching node catalogue version to ensure parameter schemas and operation semantics are correct

### Converter Versioning
- The converter itself is versioned independently (semver)
- Each conversion output includes metadata: converter version, source n8n version, timestamp, confidence score
- This enables auditing and reproducibility

---

## Internal Validation and Testing

### Snapshot Tests
- Maintain a library of n8n workflow fixtures representing common patterns
- For each fixture, store the expected ASL output
- CI pipeline runs the converter against all fixtures and compares output
- Any change to translation logic must pass all existing snapshots (or deliberately update them)

### Expression Translation Tests
- Unit tests for every entry in the expression translation table
- Property-based tests: generate random n8n expressions in Category A, translate them, verify the JSONata output produces the same result for sample inputs

### ASL Validation
- Every generated ASL definition is validated against the ASL JSON schema
- Optionally validated via `aws stepfunctions validate-state-machine-definition` API call

### Integration Tests (against real AWS)
- Small set of end-to-end tests that deploy generated Step Functions to a test AWS account and verify execution
- Run on a schedule (not every CI build) to manage cost
- Tests cover: basic linear workflow, branching (IF/Switch), Map state iteration, Merge patterns, cross-node Variables, webhook trigger via fURL, sub-workflow invocation

---

## Technology Stack

| Component | Language | Notes |
|---|---|---|
| Release parser | Python | Parses npm packages, generates catalogue |
| Workflow analyzer | Python | JSON parsing, graph analysis, report generation |
| Expression classifier | Node.js (subprocess) | AST parsing via acorn/babel for JS expressions |
| Deterministic translator | Python | Rule-based ASL generation |
| AI agent | Python | LLM integration for fallback translation |
| PicoFun integration | Python | PicoFun is a Python tool |
| GraphQL client gen | Go / Python | Separate project, integrated via CLI |
| CDK stacks | Python | CDK Python bindings |
| Lambda handlers | Python (PicoFun) / Node.js (Code nodes) / Python (utility) | Mixed runtimes as needed |
| Internal test suite | Python (pytest) | Snapshot, unit, property-based, integration tests |

---

## Future Considerations (Post-MVP)

- **Express workflows**: For high-volume, short-duration workflows. Requires cost estimation logic.
- **Binary data**: S3 offloading for file processing workflows.
- **Google / Microsoft service nodes**: PicoFun client generation for non-AWS cloud APIs.
- **Distributed Map**: For workflows processing very large datasets. S3 ItemReader/ResultWriter.
- **Zapier / Make.com import**: Additional source format parsers feeding into the same translation engine.
- **Community nodes**: Support for n8n community packages beyond `n8n-nodes-base`.
- **Visual diff tool**: Side-by-side view of n8n workflow and generated Step Functions (SaaS feature).
- **Idempotency analysis**: For Express workflow support, analyze whether API calls are safe to retry.
- **Cost estimation**: Estimate Step Functions cost based on expected execution frequency and state count.
