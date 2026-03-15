# Supported Node Types Reference

This document lists all n8n node types supported by Phaeton, the translation strategy used for each, and known limitations. Use this reference to determine which workflows can be converted to AWS Step Functions and what manual adjustments may be needed.

## Summary

| Support Level       | Count |
|---------------------|-------|
| Fully Supported     | 24    |
| Partially Supported | 4     |
| Unsupported         | 7     |

## Classification Categories

Phaeton classifies each n8n node into one of the following categories (defined by the `NodeClassification` enum in `phaeton-models`):

| Category       | Description                                              |
|----------------|----------------------------------------------------------|
| `AWS_NATIVE`   | Direct AWS service SDK integration via Step Functions     |
| `FLOW_CONTROL` | n8n control-flow nodes (branching, merging, looping)      |
| `TRIGGER`      | Workflow entry-point nodes                                |
| `CODE_JS`      | JavaScript Code nodes executed as Lambda functions        |
| `CODE_PYTHON`  | Python Code nodes executed as Lambda functions            |
| `PICOFUN_API`  | SaaS APIs translated via PicoFun client generation        |
| `GRAPHQL_API`  | GraphQL APIs translated via generated clients             |
| `UNSUPPORTED`  | Nodes with no translation strategy                        |

## Fully Supported Nodes

### Flow Control

| n8n Type | Display Name | Strategy | Limitations |
|----------|-------------|----------|-------------|
| `n8n-nodes-base.if` | IF | Choice State with JSONata conditions | None |
| `n8n-nodes-base.switch` | Switch | Choice State with multiple Choice Rules and Default | None |
| `n8n-nodes-base.noOp` | No Operation | Pass State (identity) | None |
| `n8n-nodes-base.set` | Set / Edit Fields | Pass State with JSONata Output expression | None |
| `n8n-nodes-base.executeWorkflow` | Execute Workflow | Task State (`startExecution.sync:2` SDK) | Requires SSM Parameter or CDK reference for sub-workflow ARN |

### AWS Native Services

| n8n Type | Display Name | Strategy | Limitations |
|----------|-------------|----------|-------------|
| `n8n-nodes-base.awsS3` | AWS S3 | Task State (`aws-sdk:s3`) | None |
| `n8n-nodes-base.awsDynamoDB` | AWS DynamoDB | Task State (`aws-sdk:dynamodb`) | None |
| `n8n-nodes-base.awsSqs` | AWS SQS | Task State (`aws-sdk:sqs`) | None |
| `n8n-nodes-base.awsSns` | AWS SNS | Task State (`aws-sdk:sns`) | None |
| `n8n-nodes-base.awsSes` | AWS SES | Task State (`aws-sdk:ses`) | None |
| `n8n-nodes-base.awsEventBridge` | AWS EventBridge | Task State (`aws-sdk:eventbridge`) | None |
| `n8n-nodes-base.awsLambda` | AWS Lambda | Task State (`lambda:invoke`) | None |

### Database

| n8n Type | Display Name | Strategy | Limitations |
|----------|-------------|----------|-------------|
| `n8n-nodes-base.postgres` | Postgres | Task State (RDS Data API `executeStatement`) | Requires Aurora/RDS Data API-enabled cluster |
| `n8n-nodes-base.mySql` | MySQL | Task State (RDS Data API `executeStatement`) | Requires Aurora/RDS Data API-enabled cluster |
| `n8n-nodes-base.microsoftSql` | Microsoft SQL | Task State (RDS Data API `executeStatement`) | Requires Aurora/RDS Data API-enabled cluster |

### HTTP

| n8n Type | Display Name | Strategy | Limitations |
|----------|-------------|----------|-------------|
| `n8n-nodes-base.httpRequest` | HTTP Request | Task State (`http:invoke`) | Credentials stored in SSM Parameter Store |

### SaaS Integrations

| n8n Type | Display Name | Strategy | Limitations |
|----------|-------------|----------|-------------|
| `n8n-nodes-base.slack` | Slack | Task State (`http:invoke`) via Slack API | OAuth2 token in SSM Parameter Store |
| `n8n-nodes-base.gmail` | Gmail | Task State (`http:invoke`) via Gmail API | OAuth2 token in SSM Parameter Store |
| `n8n-nodes-base.googleSheets` | Google Sheets | Task State (`http:invoke`) via Sheets API | OAuth2 token in SSM Parameter Store |
| `n8n-nodes-base.notion` | Notion | Task State (`http:invoke`) via Notion API | API key in SSM Parameter Store |
| `n8n-nodes-base.airtable` | Airtable | Task State (`http:invoke`) via Airtable API | API key in SSM Parameter Store |

### Triggers

| n8n Type | Display Name | Strategy | Limitations |
|----------|-------------|----------|-------------|
| `n8n-nodes-base.scheduleTrigger` | Schedule Trigger | EventBridge scheduled rule | None |
| `n8n-nodes-base.webhook` | Webhook | Lambda Function URL | None |
| `n8n-nodes-base.manualTrigger` | Manual Trigger | No infrastructure (manual execution) | None |

## Partially Supported Nodes

| n8n Type | Display Name | Category | Strategy | Limitations |
|----------|-------------|----------|----------|-------------|
| `n8n-nodes-base.merge` | Merge | `FLOW_CONTROL` | Parallel State (via engine post-processing) | Placeholder only; requires multi-branch join detection (TASK-0012) |
| `n8n-nodes-base.splitInBatches` | Split In Batches | `FLOW_CONTROL` | Map State (`MaxConcurrency=1`) | Requires engine post-processing to wire loop body (TASK-0013) |
| `n8n-nodes-base.loop` | Loop Over Items | `FLOW_CONTROL` | Map State (count) or Choice State (condition) | Placeholder wiring needed (TASK-0025) |
| `n8n-nodes-base.code` | Code | `CODE_JS` / `CODE_PYTHON` | Lambda Function | n8n globals (`$env`, `$execution`, `$workflow`, `$prevNode`) not fully shimmed (TASK-0014) |
| `n8n-nodes-base.wait` | Wait | `FLOW_CONTROL` | Wait State or callback Task State | Callback modes (form/webhook waits) generate Lambda handler artifacts |

## Unsupported Nodes

The following node types are recognized by the classifier but have no translator implementation. Workflows containing these nodes will produce warnings during conversion.

| n8n Type | Display Name | Category | Notes |
|----------|-------------|----------|-------|
| `n8n-nodes-base.filter` | Filter | `FLOW_CONTROL` | No translator; items-level filtering has no direct ASL equivalent |
| `n8n-nodes-base.limit` | Limit | `FLOW_CONTROL` | No translator; items-level limiting has no direct ASL equivalent |
| `n8n-nodes-base.removeDuplicates` | Remove Duplicates | `FLOW_CONTROL` | No translator |
| `n8n-nodes-base.aggregate` | Aggregate | `FLOW_CONTROL` | No translator |
| `n8n-nodes-base.splitOut` | Split Out | `FLOW_CONTROL` | No translator |
| `n8n-nodes-base.summarize` | Summarize | `FLOW_CONTROL` | No translator |
| `n8n-nodes-base.stopAndError` | Stop and Error | `FLOW_CONTROL` | No translator |

Any node type not listed above that is not recognized by the classifier will be classified as `UNSUPPORTED`. If a PicoFun AI agent is available, it may attempt a fallback translation; otherwise the node is skipped with a warning.

## Fallback Behaviors

- **Unknown trigger nodes** (type name ends in `Trigger`): Translated as Lambda Function URL webhooks with a warning.
- **PicoFun fallback**: Nodes classified as `PICOFUN_API` are translated via Lambda invocation with PicoFun-generated client code.
- **AI agent fallback**: When configured, unrecognized nodes may be translated by an AI agent service.

## Auto-Generation

This document can be regenerated from the codebase by inspecting:

- `FlowControlTranslator._DISPATCH` in `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py`
- `AWSServiceTranslator._SERVICE_REGISTRY` in `n8n-to-sfn/src/n8n_to_sfn/translators/aws_service.py`
- `CodeNodeTranslator.can_translate()` in `n8n-to-sfn/src/n8n_to_sfn/translators/code_node.py`
- `TriggerTranslator` in `n8n-to-sfn/src/n8n_to_sfn/translators/triggers.py`
- SaaS translators in `n8n-to-sfn/src/n8n_to_sfn/translators/saas/`
- `NodeClassification` enum in `shared/phaeton-models/src/phaeton_models/translator.py`
- Node registry in `workflow-analyzer/src/workflow_analyzer/classifier/registry.py`
- Translator instantiation order in `n8n-to-sfn/src/n8n_to_sfn/handler.py` (`create_default_engine()`)
