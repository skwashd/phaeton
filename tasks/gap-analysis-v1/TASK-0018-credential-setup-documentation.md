# Credential Setup Documentation

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #18

## Overview

All credentials are emitted as SSM `SecureString` parameters with placeholder values like `"<your-slack-oauth-token>"`. The user must provision fresh credentials for the new AWS deployment. The generated CDK application package needs to include clear documentation that lists every credential required by the workflow, links to relevant service credential creation pages, provides step-by-step instructions for populating each SSM parameter, and warns that the workflow will fail if placeholder values remain unreplaced.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The generated CDK application package includes a `CREDENTIALS.md` file.
2. The file lists every credential required by the workflow with its SSM parameter path.
3. Each credential entry includes a link to the relevant service's credential creation page.
4. Step-by-step instructions are provided for populating each SSM parameter via the AWS CLI or console.
5. A warning is prominently displayed about placeholder values causing workflow failures.
6. OAuth credentials include additional instructions for token endpoint setup and refresh schedule.
7. The `SSMWriter` generates the credentials documentation as part of its output.
8. `uv run pytest` passes in `packager/`.
9. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/ssm_writer.py`
- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py` (to invoke doc generation)
- `packager/tests/` (add/update tests)

### Technical Approach

1. **Add documentation generation to `SSMWriter`:**
   - Add a method `generate_credential_documentation(credentials, oauth_credentials) -> str` that returns a markdown string.
   - For each `CredentialSpec` (from `models/inputs.py` line 142):
     - Include `parameter_path`, `credential_type`, `description`, `associated_node_names`.
     - Map `credential_type` to known service documentation URLs.
   - For each `OAuthCredentialSpec` (from `models/inputs.py` line 176):
     - Include `credential_spec` fields plus `token_endpoint_url`, `refresh_schedule_expression`, `scopes`.
     - Include OAuth-specific setup instructions.

2. **Service URL mapping** (common services):
   ```python
   _CREDENTIAL_DOCS = {
       "slack": "https://api.slack.com/apps",
       "gmail": "https://console.cloud.google.com/apis/credentials",
       "notion": "https://www.notion.so/my-integrations",
       "airtable": "https://airtable.com/create/tokens",
       # ...
   }
   ```

3. **SSM CLI instructions:**
   ```bash
   aws ssm put-parameter \
     --name "/phaeton/credentials/slack/oauth-token" \
     --type SecureString \
     --value "xoxb-your-actual-token"
   ```

4. **Integration with CDK writer:**
   - In `CDKWriter.write` (line 27), after generating the CDK stack, call the documentation generator.
   - Write the `CREDENTIALS.md` file to the output directory alongside the CDK code.

### Testing Requirements

- Test documentation generation with standard credentials.
- Test documentation generation with OAuth credentials.
- Test with no credentials (should produce a minimal document stating no credentials needed).
- Verify all SSM parameter paths appear in the generated documentation.
- Verify placeholder values are mentioned with warnings.
