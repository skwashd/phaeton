# Phaeton Pipeline Deployment Guide

This guide covers deploying the Phaeton conversion pipeline as managed AWS infrastructure using CDK.

## Overview

The `deployment/` component is a CDK application that deploys the entire Phaeton pipeline as interconnected AWS services. It creates Lambda functions for each pipeline stage, a Step Functions state machine for orchestration, S3 buckets for artifacts, and EventBridge scheduling for automated catalog updates.

## Prerequisites

- **Python 3.14+**
- **Node.js 20+** (required by AWS CDK CLI)
- **AWS CDK CLI:** `npm install -g aws-cdk`
- **AWS credentials** configured via `aws configure` or environment variables
- **CDK bootstrap** completed for your target account and region

## Architecture

The deployment creates 6 CDK stacks:

```
┌─────────────────────────────────────────────────────────────┐
│  PhaetonReleaseParser                                       │
│  Lambda + S3 (CatalogBucket) + EventBridge (daily schedule) │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PhaetonWorkflowAnalyzer                                    │
│  Lambda                                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PhaetonAiAgent                                             │
│  Lambda + Bedrock IAM permissions                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PhaetonTranslationEngine                                   │
│  Lambda (depends on AI Agent for fallback invocation)       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PhaetonPackager                                            │
│  Lambda + S3 (OutputBucket) + 1 GiB ephemeral storage       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  PhaetonOrchestration                                       │
│  Step Functions state machine + Adapter Lambda              │
└─────────────────────────────────────────────────────────────┘
```

## Pipeline Flow

The Step Functions state machine (`phaeton-conversion-pipeline`) orchestrates the conversion:

```
PrepareInput (Pass) ─► AnalyzeWorkflow (Lambda) ─► AdaptForTranslation (Adapter Lambda)
    ─► TranslateWorkflow (Lambda) ─► AdaptForPackaging (Adapter Lambda)
    ─► PackageWorkflow (Lambda) ─► Success
```

The Adapter Lambda bridges data format differences between pipeline stages, converting `ConversionReport` to `WorkflowAnalysis` and `TranslationOutput` to `PackagerInput`.

All Lambda invocations include automatic retry on service exceptions. The overall state machine timeout is 30 minutes.

## Deployment Commands

```bash
# Navigate to deployment directory
cd deployment

# Install dependencies
uv sync

# List all stacks
uv run cdk list

# Synthesize CloudFormation templates (verify before deploying)
uv run cdk synth

# Deploy all stacks
uv run cdk deploy --all

# Deploy a specific stack
uv run cdk deploy PhaetonReleaseParser
```

## Configuration

### Environment Variables

| Lambda | Variable | Purpose |
|--------|----------|---------|
| phaeton-release-parser | `CATALOG_BUCKET` | S3 bucket for n8n node catalog storage |
| phaeton-translation-engine | `AI_AGENT_FUNCTION_NAME` | AI Agent Lambda name for fallback invocation |
| phaeton-packager | `OUTPUT_BUCKET` | S3 bucket for generated CDK application output |

### Memory and Timeout Settings

| Lambda | Memory | Timeout |
|--------|--------|---------|
| phaeton-release-parser | 512 MB | 120 seconds |
| phaeton-workflow-analyzer | 512 MB | 120 seconds |
| phaeton-ai-agent | 1024 MB | 120 seconds |
| phaeton-translation-engine | 512 MB | 300 seconds |
| phaeton-packager | 1024 MB | 300 seconds |
| phaeton-adapter | 256 MB | 30 seconds |

All Lambda functions use Python 3.13 runtime with ARM64 architecture.

## AWS Resource Summary

| Resource Type | Count | Details |
|---------------|-------|---------|
| Lambda Functions | 6 | One per pipeline stage + adapter |
| S3 Buckets | 2 | Catalog storage + CDK output |
| Step Functions State Machine | 1 | Pipeline orchestration (30-min timeout) |
| EventBridge Rules | 1 | Daily Release Parser schedule |
| IAM Roles | 7 | One per Lambda + one for state machine |

## First-Time Deployment

1. **Bootstrap CDK** for your target AWS account and region:

   ```bash
   cdk bootstrap aws://ACCOUNT_ID/REGION
   ```

2. **Deploy all stacks:**

   ```bash
   cd deployment
   uv sync
   uv run cdk deploy --all
   ```

   CDK will show you the resources it plans to create and ask for confirmation.

3. **Verify resources** in the AWS Console:
   - Check Lambda functions exist in the Lambda console
   - Check the Step Functions state machine in the Step Functions console
   - Check S3 buckets were created

4. **Test the pipeline** by starting a state machine execution with a sample workflow:

   ```bash
   aws stepfunctions start-execution \
     --state-machine-arn arn:aws:states:REGION:ACCOUNT_ID:stateMachine:phaeton-conversion-pipeline \
     --input '{"workflow_name": "test", "workflow": { ... }}'
   ```

## Running Tests

```bash
cd deployment
uv sync
uv run pytest
```

The test suite validates that all 6 stacks synthesize correctly and produce the expected resources.
