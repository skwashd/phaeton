# Getting Started with Phaeton

Phaeton converts n8n workflow JSON exports into deployable AWS Step Functions CDK applications. This guide walks you through installation, converting your first workflow, and deploying the result.

## Prerequisites

Install the following tools before proceeding:

| Tool | Version | Purpose |
|------|---------|---------|
| [Python](https://www.python.org/downloads/) | 3.14+ | Runtime for all components |
| [uv](https://docs.astral.sh/uv/) | Latest | Python package manager |
| [Node.js](https://nodejs.org/) | 20+ | Required by AWS CDK CLI |
| [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html) | Latest | `npm install -g aws-cdk` |
| [AWS CLI](https://aws.amazon.com/cli/) | v2 | AWS credential configuration |

Verify your setup:

```bash
python3 --version   # 3.14+
uv --version
node --version       # v20+
cdk --version
aws --version
```

### AWS Credentials

Configure AWS credentials so that CDK can deploy resources:

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, region, and output format.
```

Alternatively, use environment variables or an AWS profile. The CDK deploy step requires valid credentials with permissions to create Step Functions, Lambda functions, IAM roles, and SSM parameters.

## Installation

Clone the repository and install each component:

```bash
git clone <repository-url>
cd phaeton/end-to-end

# Install all components
cd shared/phaeton-models && uv sync && cd ../..
cd n8n-release-parser && uv sync && cd ..
cd workflow-analyzer && uv sync && cd ..
cd n8n-to-sfn && uv sync && cd ..
cd packager && uv sync && cd ..
cd node-translator && uv sync && cd ..
cd expression-translator && uv sync && cd ..
cd spec-registry && uv sync && cd ..
cd deployment && uv sync && cd ..
```

To verify the installation, run the test suite for any component:

```bash
cd workflow-analyzer && uv run pytest && cd ..
```

## Quick Start: Managed Pipeline

The primary way to use Phaeton is via the managed AWS pipeline. Once [deployed](deployment.md), the Step Functions state machine handles the entire conversion.

### Start a Conversion

Submit a workflow JSON to the `phaeton-conversion-pipeline` state machine:

```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT_ID:stateMachine:phaeton-conversion-pipeline \
  --input "$(cat <<'EOF'
{
  "workflow_name": "my-workflow",
  "workflow": {
    "name": "my-workflow",
    "nodes": [...],
    "connections": {...},
    "settings": {"executionOrder": "v1"}
  }
}
EOF
)"
```

The pipeline runs through analysis, translation, and packaging automatically. Monitor progress in the [Step Functions console](https://console.aws.amazon.com/states/).

### Download the Output

When the execution succeeds, the output contains the S3 location of the zip:

```json
{
  "status": "success",
  "s3_bucket": "phaeton-output-bucket-...",
  "s3_key": "packages/my-workflow.zip",
  "workflow_name": "my-workflow"
}
```

Download and extract:

```bash
aws s3 cp s3://{bucket}/packages/my-workflow.zip .
unzip my-workflow.zip -d my-workflow
```

### Deploy the Output

1. Populate SSM parameters per `CREDENTIALS.md` in the extracted zip:
   ```bash
   aws ssm put-parameter --name "/phaeton/creds/{name}" --value "..." --type SecureString
   ```

2. Validate and deploy:
   ```bash
   cd my-workflow/cdk
   uv sync
   uv run cdk synth    # validate
   uv run cdk deploy   # deploy to AWS
   ```

3. Test in the [Step Functions console](https://console.aws.amazon.com/states/) — start an execution and verify the output.

For a detailed walkthrough of the pipeline stages and data transformations, see the [Workflow Guide](workflow-guide.md).

---

## Local Development Flow

For development and testing, you can run each pipeline stage locally via CLI. This section walks through converting a simple n8n workflow into a deployable CDK application using all four pipeline stages.

### 1. Prepare a Sample Workflow

Save the following n8n workflow JSON to a file called `my-workflow.json`:

```json
{
  "name": "simple_dynamodb_test",
  "nodes": [
    {
      "id": "00000000-0001-4000-8000-000000000001",
      "name": "ManualTrigger",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1,
      "position": [250, 300],
      "parameters": {}
    },
    {
      "id": "00000000-0002-4000-8000-000000000002",
      "name": "GenerateData",
      "type": "n8n-nodes-base.code",
      "typeVersion": 1,
      "position": [450, 300],
      "parameters": {
        "language": "python",
        "pythonCode": "return [{'json': {'pk': 'test-item-001', 'message': 'hello from phaeton', 'status': 'ok'}}]"
      }
    },
    {
      "id": "00000000-0003-4000-8000-000000000003",
      "name": "DDBPut",
      "type": "n8n-nodes-base.awsDynamoDB",
      "typeVersion": 1,
      "position": [650, 300],
      "parameters": {
        "resource": "item",
        "operation": "create",
        "tableName": "PhaetonTestTable",
        "additionalFields": {}
      }
    }
  ],
  "connections": {
    "ManualTrigger": {
      "main": [
        [{"node": "GenerateData", "type": "main", "index": 0}]
      ]
    },
    "GenerateData": {
      "main": [
        [{"node": "DDBPut", "type": "main", "index": 0}]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

This workflow has three nodes: a manual trigger, a code node that generates data, and a DynamoDB PutItem operation.

### 2. Build the Node Catalog (Component 1 — n8n Release Parser)

The release parser fetches n8n node type definitions from npm and builds a catalog used by later stages:

```bash
cd n8n-release-parser
uv run n8n-release-parser fetch-releases --months 6
```

This lists the recent n8n-nodes-base releases available. The catalog provides node metadata that enriches the analysis and translation stages.

### 3. Analyze the Workflow (Component 2 — Workflow Analyzer)

The workflow analyzer classifies nodes, builds a dependency graph, analyzes expressions, and produces a feasibility report:

```bash
cd ../workflow-analyzer
uv run workflow-analyzer ../my-workflow.json -o ../analysis/
```

This generates two report files in the `analysis/` directory:
- `analysis.json` — structured analysis data (used by the translation engine)
- `analysis.md` — human-readable feasibility report with a confidence score

Review `analysis.md` to see which nodes are supported, any blocking issues, and the overall conversion confidence.

### 4. Translate the Workflow (Component 3 — Translation Engine)

The translation engine (`n8n-to-sfn`) is a library, not a standalone CLI. It converts the analyzed workflow into an AWS Step Functions ASL definition and Lambda function artifacts. It is called programmatically or through the packager.

For a direct programmatic invocation:

```python
from n8n_to_sfn.handler import create_default_engine

engine = create_default_engine()
output = engine.translate(analysis)
```

The `create_default_engine()` factory registers all built-in translators (flow control, AWS services, triggers, code nodes, SaaS integrations) in the correct priority order. In the standard pipeline flow, the packager handles this step. If you have a `PackagerInput` JSON file (produced by the deployment orchestration or by scripting the translation engine), proceed to the next step.

### 5. Package into a CDK Application (Component 4 — Packager)

The packager takes the translation output and generates a complete, deployable CDK application:

```bash
cd ../packager
uv run python -m n8n_to_sfn_packager --input <translation_output.json> -o ../output/
```

Replace `<translation_output.json>` with the path to your PackagerInput JSON file.

## Understanding the Output

Whether you use the managed pipeline (zip from S3) or the local CLI flow (directory on disk), the output has the same structure:

```
{workflow_name}/
├── statemachine/
│   └── definition.asl.json          # AWS Step Functions ASL definition
├── lambdas/
│   └── {function_name}/
│       ├── handler.py                # Lambda function code
│       └── requirements.txt          # Function dependencies (if any)
├── cdk/
│   ├── app.py                        # CDK application entry point
│   ├── stacks/
│   │   └── workflow_stack.py         # CDK stack defining all AWS resources
│   ├── pyproject.toml                # CDK project dependencies
│   └── cdk.json                      # CDK configuration
├── MIGRATE.md                        # Migration checklist and manual steps
├── CREDENTIALS.md                    # SSM parameter setup instructions
├── README.md                         # Deployment instructions for this workflow
└── reports/
    ├── conversion_report.json        # Machine-readable conversion report
    └── conversion_report.md          # Human-readable conversion report
```

Key files:
- **`definition.asl.json`** — the Step Functions state machine definition in Amazon States Language.
- **`cdk/app.py`** — the CDK application entry point that deploys the state machine, Lambda functions, and supporting resources.
- **`MIGRATE.md`** — a checklist of manual steps required after deployment (e.g., setting up credentials in SSM Parameter Store).
- **`CREDENTIALS.md`** — lists all SSM parameters that need to be populated with credential values before deployment.
- **`reports/conversion_report.md`** — human-readable summary of conversion results, including any warnings or AI-assisted translations that need review.

When using the managed pipeline, this directory is zipped and uploaded to `s3://{OUTPUT_BUCKET}/packages/{workflow_name}.zip`.

## Deploying the Output

This section covers deploying the *generated CDK application* (the output of Phaeton). To deploy the *Phaeton pipeline itself*, see [Deployment Guide](deployment.md).

### Bootstrap CDK (First Time Only)

If you have not used CDK in your target AWS account and region, bootstrap it first:

```bash
cdk bootstrap aws://ACCOUNT_ID/REGION
```

### Populate SSM Parameters

Before deploying, populate any SSM parameters referenced by the workflow. Check the generated `CREDENTIALS.md` for the list of required parameters and their expected values:

```bash
aws ssm put-parameter --name "/phaeton/creds/{name}" --value "your-secret" --type SecureString
```

### Validate with CDK Synth

Verify the generated CDK application synthesizes correctly:

```bash
cd {workflow_name}/cdk
uv sync
uv run cdk synth
```

This produces a CloudFormation template without deploying anything. Review the output for any errors.

### Deploy

Deploy the converted workflow to your AWS account:

```bash
uv run cdk deploy
```

CDK will show you the resources it plans to create and ask for confirmation. After deployment, your Step Functions state machine is live.

### Test the Deployed State Machine

1. Open the [AWS Step Functions console](https://console.aws.amazon.com/states/).
2. Find your newly deployed state machine.
3. Click **Start execution** to run it.
4. Review the execution graph and output to verify the workflow behaves as expected.

## Troubleshooting

### `uv sync` fails with dependency resolution errors

Ensure you are running `uv sync` from within each component directory, not from the repository root. Each component has its own `pyproject.toml` with independent dependencies.

```bash
# Correct
cd n8n-release-parser && uv sync

# Incorrect — do not run from the repo root for individual components
uv sync
```

### Python version mismatch

All components require Python 3.14+. If you see version errors:

```bash
python3 --version
# If too old, install the correct version and ensure uv picks it up:
uv python install 3.14
```

### `cdk synth` fails

- Ensure Node.js 20+ is installed (`node --version`).
- Ensure the CDK CLI is installed globally (`npm install -g aws-cdk`).
- Check that `requirements.txt` dependencies in the generated `cdk/` directory are installed.

### AWS credential errors during deploy

- Run `aws sts get-caller-identity` to verify your credentials are configured.
- Ensure your IAM user/role has permissions for Step Functions, Lambda, IAM, and SSM.
- If using a specific profile: `export AWS_PROFILE=your-profile-name`.

### Workflow analysis reports low confidence

A low confidence score means some nodes in your workflow may not have full translation support. Check:
- `analysis.md` for the list of unsupported or partially-supported nodes.
- The `blocking_issues` section for issues that prevent conversion.
- Consider simplifying the workflow or manually implementing unsupported nodes as Lambda functions.

### Import errors when running components

If you see `ModuleNotFoundError`, the component dependencies may not be installed:

```bash
cd <component-directory>
uv sync
```

## Deploying the Phaeton Pipeline

The Phaeton pipeline itself can be deployed as a managed AWS service using CDK. This deploys Lambda functions for each component, a Step Functions state machine for orchestration, S3 buckets for artifacts, and EventBridge scheduling for automated catalog updates.

See the [Deployment Guide](deployment.md) for full instructions.

## AI Translator Fallback

For n8n nodes and expressions that cannot be translated deterministically, Phaeton includes two AI-powered translator components — node-translator and expression-translator — powered by Amazon Bedrock. Both use the Strands Agents SDK with Claude Sonnet 4 to generate ASL state definitions and JSONata expressions respectively.

See the [AI Translator Guide](ai-translators.md) for configuration, security details, and integration information.

## Next Steps

- Read the [Architecture Reference](architecture.md) for component details, operational concerns, and extensibility.
- Trace the full data flow in the [Workflow Guide](workflow-guide.md).
- Review [Supported Node Types](supported-node-types.md) to see which n8n nodes are translatable.
- Run the full test suite to verify your setup: `cd <component> && uv run pytest`.
