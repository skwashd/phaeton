# Custom Domain Webhooks

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #29

## Overview

Lambda Function URLs generate random AWS-assigned domains. For the initial version, Function URLs are sufficient. Custom domain support (via CloudFront or API Gateway) is deferred to a future iteration to avoid the additional complexity and configuration overhead that API Gateway introduces. This task adds the optional capability for users who need stable, branded webhook endpoints.

## Dependencies

- **Blocked by:** TASK-0027 (webhook authentication should be in place first)
- **Blocks:** None

## Acceptance Criteria

1. The generated CDK stack optionally includes a CloudFront distribution or API Gateway in front of webhook Function URLs.
2. Custom domain support is opt-in via CDK context variables (e.g., `custom_domain`, `certificate_arn`).
3. When disabled (default), Function URLs are used directly with no additional infrastructure.
4. When enabled, a Route 53 alias record, ACM certificate reference, and CloudFront distribution are generated.
5. Webhook URLs in the generated documentation reflect the custom domain when configured.
6. `uv run pytest` passes in `packager/`.
7. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`
- `packager/tests/` (update/add tests)

### Technical Approach

1. **CloudFront approach (recommended over API Gateway for simplicity):**
   ```python
   if custom_domain:
       distribution = cloudfront.Distribution(self, "WebhookCDN",
           default_behavior=cloudfront.BehaviorOptions(
               origin=origins.HttpOrigin(function_url_domain),
           ),
           domain_names=[custom_domain],
           certificate=acm.Certificate.from_certificate_arn(self, "Cert", cert_arn),
       )
       route53.ARecord(self, "WebhookAlias",
           zone=hosted_zone,
           target=route53.RecordTarget.from_alias(targets.CloudFrontTarget(distribution)),
       )
   ```

2. **Context variables:**
   - `custom_domain`: The custom domain name (e.g., `webhooks.example.com`).
   - `certificate_arn`: ACM certificate ARN for the custom domain.
   - `hosted_zone_id`: Route 53 hosted zone ID.

3. **Conditional generation:**
   - The CDK writer checks `self.node.try_get_context("custom_domain")`.
   - If present, generates CloudFront + Route 53 constructs.
   - If absent, generates only Function URLs (current behavior).

### Testing Requirements

- Test CDK code generation with custom domain enabled.
- Test CDK code generation with custom domain disabled (default behavior unchanged).
- Test that all required CDK imports are included when custom domain is enabled.
