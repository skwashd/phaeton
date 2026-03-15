# Iam Wildcard Resource Arns

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #9

## Overview

The `_collect_sdk_actions()` method in `iam_writer.py` constructs ARNs with empty region and account fields:

```python
resource_arn = f"arn:aws:{service.lower()}:::*"
```

This produces ARNs like `arn:aws:dynamodb:::*` — granting access to all resources of a service across all accounts and regions. Production IAM policies should scope resources to at minimum `arn:aws:{service}:*:*:*` (any region, any account, any resource of that service), and ideally to specific resource types using CDK context variables for region and account.

## Dependencies

- **Blocked by:** TASK-0004 (syntax error must be fixed first so the module can be imported)
- **Blocks:** None

## Acceptance Criteria

1. Generated IAM policy resource ARNs include region and account placeholders: at minimum `arn:aws:{service}:*:*:*`.
2. Ideally, ARNs use CDK intrinsics: `f"arn:aws:{service}:{Aws.REGION}:{Aws.ACCOUNT_ID}:*"` or equivalent.
3. For services where the resource type is known (e.g., DynamoDB tables, S3 buckets), the ARN pattern includes the resource type segment.
4. The `_collect_sdk_actions` method (line 198) returns properly formatted ARNs.
5. `uv run pytest` passes in `packager/`.
6. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/iam_writer.py`

### Technical Approach

1. In `_collect_sdk_actions` (line 198), change line 215 from:
   ```python
   resource_arn = f"arn:aws:{service.lower()}:::*"
   ```
   to:
   ```python
   resource_arn = f"arn:aws:{service.lower()}:*:*:*"
   ```

2. For a more refined approach, create a service-to-ARN-pattern mapping for common services:
   ```python
   _SERVICE_ARN_PATTERNS = {
       "dynamodb": "arn:aws:dynamodb:*:*:table/*",
       "s3": "arn:aws:s3:::*",  # S3 is global, no region/account
       "sqs": "arn:aws:sqs:*:*:*",
       "sns": "arn:aws:sns:*:*:*",
       "lambda": "arn:aws:lambda:*:*:function:*",
       "states": "arn:aws:states:*:*:stateMachine:*",
   }
   ```
   Fall back to `arn:aws:{service}:*:*:*` for unmapped services.

3. In the generated CDK code, consider using `cdk.Aws.REGION` and `cdk.Aws.ACCOUNT_ID` instead of wildcards where the IAM policy is stack-scoped.

### Testing Requirements

- Update tests for `_collect_sdk_actions` to verify the new ARN format.
- Test with multiple services (DynamoDB, S3, SQS, SNS) to verify correct ARN patterns.
- Test the fallback for unknown services.
- Verify that `_make_statement` (line 221) correctly uses the new ARNs.
