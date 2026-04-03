# Deploying Phaeton

Step-by-step guide for deploying the Phaeton n8n-to-Step Functions conversion pipeline into an AWS account.

## Prerequisites

Install the following tools before proceeding:

| Tool | Minimum version | Install |
|------|----------------|---------|
| Python | 3.14 | <https://docs.python.org/3/using/> |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20 | <https://nodejs.org/> (required by AWS CDK CLI) |
| AWS CDK CLI | latest | `npm install -g aws-cdk` |
| AWS CLI | 2.x | <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html> |
| Docker Desktop | latest | <https://www.docker.com/products/docker-desktop/> (must be running during deploy) |

## 1. Configure AWS credentials

Configure your CLI for the target account and region (this guide assumes `us-east-1`):

```bash
aws configure
```

Verify access:

```bash
aws sts get-caller-identity
```

## 2. Enable Bedrock model access

The node-translator and expression-translator Lambdas invoke Amazon Bedrock foundation models. Model access must be enabled manually because it requires EULA acceptance, which has no CLI equivalent.

1. Open the [Amazon Bedrock Model Access](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess) console page.
2. Click **Manage model access**.
3. Enable **Anthropic > Claude 3.5 Sonnet** (or whichever model your agents are configured to use).
4. Submit and wait for the status to show **Access granted**.

Verify with:

```bash
aws bedrock get-foundation-model \
  --model-identifier anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --region us-east-1
```

## 3. Bootstrap CDK

CDK bootstrap provisions an S3 bucket and IAM roles that CDK uses to deploy assets:

```bash
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/us-east-1
```

## 4. Install dependencies

From the `deployment/` directory:

```bash
cd deployment
uv sync
```

## 5. Synthesize

Generate CloudFormation templates to verify everything resolves correctly. Docker must be running for asset bundling:

```bash
uv run cdk synth
```

This produces templates in `cdk.out/`. Review the output for errors before deploying.

## 6. Deploy

Deploy all stacks. The `--require-approval broadening` flag prompts for confirmation only when IAM permissions are widened:

```bash
uv run cdk deploy --all --require-approval broadening
```

CDK deploys the following stacks:

| Stack | Key resources |
|-------|--------------|
| PhaetonReleaseParser | Lambda, S3 catalog bucket, EventBridge daily schedule |
| PhaetonSpecRegistry | Lambda, KMS-encrypted S3 spec bucket, S3 event notifications |
| PhaetonWorkflowAnalyzer | Lambda |
| PhaetonNodeTranslator | Lambda with Bedrock InvokeModel permission |
| PhaetonExpressionTranslator | Lambda with Bedrock InvokeModel permission |
| PhaetonTranslationEngine | Lambda with invoke permissions on both translator Lambdas |
| PhaetonPackager | Lambda, S3 output bucket, 1 GiB ephemeral storage |
| PhaetonOrchestration | Adapter Lambda, Step Functions state machine |

## 7. Verify deployment

List deployed Lambda functions:

```bash
aws lambda list-functions \
  --query "Functions[?starts_with(FunctionName, 'phaeton-')].FunctionName" \
  --output table
```

Expected functions: `phaeton-release-parser`, `phaeton-workflow-analyzer`, `phaeton-node-translator`, `phaeton-expression-translator`, `phaeton-translation-engine`, `phaeton-packager`, `phaeton-adapter`, `phaeton-spec-indexer`.

List the state machine:

```bash
aws stepfunctions list-state-machines \
  --query "stateMachines[?name=='phaeton-conversion-pipeline']" \
  --output table
```

List S3 buckets:

```bash
aws s3 ls | grep phaeton
```

## 8. Run a test conversion

Start an execution of the conversion pipeline with the sample n8n workflow in `examples/test-workflow.json`:

```bash
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
  --query "stateMachines[?name=='phaeton-conversion-pipeline'].stateMachineArn" \
  --output text)

aws stepfunctions start-execution \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --input file://examples/test-workflow.json
```

Poll for completion:

```bash
EXECUTION_ARN=$(aws stepfunctions list-executions \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --max-results 1 \
  --query "executions[0].executionArn" \
  --output text)

aws stepfunctions describe-execution \
  --execution-arn "$EXECUTION_ARN" \
  --query "{status: status, output: output}"
```

When the status is `SUCCEEDED`, the output contains an S3 location. Download the generated CDK project:

```bash
OUTPUT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name PhaetonPackager \
  --query "Stacks[0].Outputs[?OutputKey=='OutputBucketName'].OutputValue" \
  --output text 2>/dev/null || \
  aws s3 ls | grep -o 'phaetonpackager-outputbucket[^ ]*')

aws s3 cp "s3://${OUTPUT_BUCKET}/my-test-workflow/" ./output/ --recursive
```

## Teardown

To remove all deployed resources:

```bash
cd deployment
uv run cdk destroy --all
```

S3 buckets with `RETAIN` removal policy (catalog and spec buckets) are not deleted automatically. Empty and delete them manually if needed:

```bash
aws s3 rb s3://BUCKET_NAME --force
```
