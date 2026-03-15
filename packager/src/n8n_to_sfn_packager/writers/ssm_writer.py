"""SSM Parameter Store writer.

Generates SSM parameter definitions and credential setup documentation
from credential and OAuth credential specs.
"""

from __future__ import annotations

from n8n_to_sfn_packager.models.inputs import CredentialSpec, OAuthCredentialSpec
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition

_CREDENTIAL_DOCS: dict[str, str] = {
    "slack": "https://api.slack.com/apps",
    "gmail": "https://console.cloud.google.com/apis/credentials",
    "googlesheets": "https://console.cloud.google.com/apis/credentials",
    "notion": "https://www.notion.so/my-integrations",
    "airtable": "https://airtable.com/create/tokens",
    "github": "https://github.com/settings/tokens",
    "jira": "https://id.atlassian.com/manage-profile/security/api-tokens",
    "hubspot": "https://developers.hubspot.com/docs/api/private-apps",
    "stripe": "https://dashboard.stripe.com/apikeys",
    "twilio": "https://www.twilio.com/console",
    "sendgrid": "https://app.sendgrid.com/settings/api_keys",
    "mailchimp": "https://mailchimp.com/developer/marketing/guides/quick-start/#generate-your-api-key",
    "shopify": "https://partners.shopify.com/",
    "dropbox": "https://www.dropbox.com/developers/apps",
    "asana": "https://app.asana.com/0/developer-console",
    "trello": "https://trello.com/power-ups/admin",
    "discord": "https://discord.com/developers/applications",
    "telegram": "https://core.telegram.org/bots#botfather",
    "openai": "https://platform.openai.com/api-keys",
}


class SSMWriter:
    """Generates SSM parameter definitions and credential documentation."""

    def generate_parameter_definitions(
        self,
        credentials: list[CredentialSpec],
        oauth_credentials: list[OAuthCredentialSpec],
    ) -> list[SSMParameterDefinition]:
        """Produce SSM parameter definitions for all credentials.

        Standard credentials produce one parameter each. OAuth credentials
        produce two parameters (access token and refresh token).

        Args:
            credentials: Standard credential specs.
            oauth_credentials: OAuth2 credential specs.

        Returns:
            List of SSM parameter definitions for the CDK stack.

        """
        params: list[SSMParameterDefinition] = []

        for cred in credentials:
            params.append(self._standard_parameter(cred))

        for oauth in oauth_credentials:
            params.extend(self._oauth_parameters(oauth))

        return params

    @staticmethod
    def _standard_parameter(cred: CredentialSpec) -> SSMParameterDefinition:
        """Create a single SSM parameter definition for a standard credential."""
        placeholder = (
            cred.placeholder_value or f"<your-{cred.credential_type}-credential>"
        )
        return SSMParameterDefinition(
            parameter_path=cred.parameter_path,
            description=cred.description
            or f"{cred.credential_type} credential for {', '.join(cred.associated_node_names)}",
            placeholder_value=placeholder,
        )

    @staticmethod
    def _oauth_parameters(oauth: OAuthCredentialSpec) -> list[SSMParameterDefinition]:
        """Create paired access/refresh token SSM parameter definitions."""
        base_path = oauth.credential_spec.parameter_path.rstrip("/")
        base_desc = oauth.credential_spec.description or "OAuth2 credential"
        nodes = (
            ", ".join(oauth.credential_spec.associated_node_names)
            if oauth.credential_spec.associated_node_names
            else "OAuth2 client"
        )

        return [
            SSMParameterDefinition(
                parameter_path=f"{base_path}/access_token",
                description=f"Access token for {base_desc} ({nodes})",
                placeholder_value="<oauth2-access-token>",
            ),
            SSMParameterDefinition(
                parameter_path=f"{base_path}/refresh_token",
                description=f"Refresh token for {base_desc} ({nodes})",
                placeholder_value="<oauth2-refresh-token>",
            ),
        ]

    def generate_credential_documentation(
        self,
        credentials: list[CredentialSpec],
        oauth_credentials: list[OAuthCredentialSpec],
    ) -> str:
        """Generate a CREDENTIALS.md markdown document.

        Lists every credential required by the workflow with its SSM
        parameter path, setup instructions, and links to service
        credential creation pages.

        Args:
            credentials: Standard credential specs.
            oauth_credentials: OAuth2 credential specs.

        Returns:
            Markdown string for CREDENTIALS.md.

        """
        lines: list[str] = []
        lines.append("# Credential Setup Guide")
        lines.append("")
        lines.append(
            "> **WARNING:** This workflow uses SSM SecureString parameters "
            "with placeholder values. The workflow **will fail** at runtime "
            "if any placeholder values remain unreplaced. You must provision "
            "real credentials for every parameter listed below before "
            "deploying.",
        )
        lines.append("")

        if not credentials and not oauth_credentials:
            lines.append(
                "This workflow does not require any credentials.",
            )
            lines.append("")
            return "\n".join(lines)

        lines.append("## General Instructions")
        lines.append("")
        lines.append(
            "Each credential is stored as an SSM SecureString parameter. "
            "Use the AWS CLI or the AWS Console to populate each parameter "
            "with a real value.",
        )
        lines.append("")
        lines.append("**AWS CLI example:**")
        lines.append("")
        lines.append("```bash")
        lines.append("aws ssm put-parameter \\")
        lines.append('  --name "/your/parameter/path" \\')
        lines.append("  --type SecureString \\")
        lines.append('  --value "your-actual-secret-value"')
        lines.append("```")
        lines.append("")
        lines.append(
            "To update an existing parameter, add the `--overwrite` flag.",
        )
        lines.append("")

        if credentials:
            lines.append("## Standard Credentials")
            lines.append("")
            for cred in credentials:
                self._write_standard_credential_section(lines, cred)

        if oauth_credentials:
            lines.append("## OAuth Credentials")
            lines.append("")
            lines.append(
                "OAuth credentials require additional setup for token "
                "endpoint configuration and automatic refresh. Each OAuth "
                "credential produces two SSM parameters (access token and "
                "refresh token) and an EventBridge-scheduled Lambda for "
                "automatic token rotation.",
            )
            lines.append("")
            for oauth in oauth_credentials:
                self._write_oauth_credential_section(lines, oauth)

        return "\n".join(lines)

    @staticmethod
    def _credential_docs_url(credential_type: str) -> str | None:
        """Look up the documentation URL for a credential type."""
        key = credential_type.lower().replace(" ", "").replace("_", "")
        # Strip common suffixes to match the mapping
        for suffix in ("api", "oauth2", "oauth", "apikey", "key", "token"):
            stripped = key.removesuffix(suffix)
            if stripped and stripped in _CREDENTIAL_DOCS:
                return _CREDENTIAL_DOCS[stripped]
        return _CREDENTIAL_DOCS.get(key)

    def _write_standard_credential_section(
        self,
        lines: list[str],
        cred: CredentialSpec,
    ) -> None:
        """Append a markdown section for a standard credential."""
        description = cred.description or cred.credential_type
        lines.append(f"### {description}")
        lines.append("")
        lines.append(f"- **SSM Parameter Path:** `{cred.parameter_path}`")
        lines.append(f"- **Credential Type:** `{cred.credential_type}`")
        placeholder = (
            cred.placeholder_value or f"<your-{cred.credential_type}-credential>"
        )
        lines.append(f"- **Placeholder Value:** `{placeholder}`")
        if cred.associated_node_names:
            nodes = ", ".join(cred.associated_node_names)
            lines.append(f"- **Used by nodes:** {nodes}")
        docs_url = self._credential_docs_url(cred.credential_type)
        if docs_url:
            lines.append(f"- **Create credential:** <{docs_url}>")
        lines.append("")
        lines.append("```bash")
        lines.append("aws ssm put-parameter \\")
        lines.append(f'  --name "{cred.parameter_path}" \\')
        lines.append("  --type SecureString \\")
        lines.append(f'  --value "<replace with your {cred.credential_type} value>"')
        lines.append("```")
        lines.append("")

    def _write_oauth_credential_section(
        self,
        lines: list[str],
        oauth: OAuthCredentialSpec,
    ) -> None:
        """Append a markdown section for an OAuth credential."""
        cred = oauth.credential_spec
        description = cred.description or cred.credential_type
        lines.append(f"### {description}")
        lines.append("")
        base_path = cred.parameter_path.rstrip("/")
        lines.append(f"- **SSM Parameter Path (access token):** `{base_path}/access_token`")
        lines.append(f"- **SSM Parameter Path (refresh token):** `{base_path}/refresh_token`")
        lines.append(f"- **Credential Type:** `{cred.credential_type}`")
        if cred.associated_node_names:
            nodes = ", ".join(cred.associated_node_names)
            lines.append(f"- **Used by nodes:** {nodes}")
        docs_url = self._credential_docs_url(cred.credential_type)
        if docs_url:
            lines.append(f"- **Create credential:** <{docs_url}>")
        lines.append(f"- **Token Endpoint URL:** `{oauth.token_endpoint_url}`")
        lines.append(f"- **Refresh Schedule:** `{oauth.refresh_schedule_expression}`")
        if oauth.scopes:
            scopes = ", ".join(f"`{s}`" for s in oauth.scopes)
            lines.append(f"- **Scopes:** {scopes}")
        lines.append("")
        lines.append("**Setup steps:**")
        lines.append("")
        lines.append(
            "1. Register your application with the service provider and "
            "obtain a client ID and client secret.",
        )
        lines.append(
            "2. Complete the OAuth authorization flow to obtain an initial "
            "access token and refresh token.",
        )
        lines.append("3. Store the tokens in SSM:")
        lines.append("")
        lines.append("```bash")
        lines.append("aws ssm put-parameter \\")
        lines.append(f'  --name "{base_path}/access_token" \\')
        lines.append("  --type SecureString \\")
        lines.append('  --value "<your-oauth2-access-token>"')
        lines.append("")
        lines.append("aws ssm put-parameter \\")
        lines.append(f'  --name "{base_path}/refresh_token" \\')
        lines.append("  --type SecureString \\")
        lines.append('  --value "<your-oauth2-refresh-token>"')
        lines.append("```")
        lines.append("")
        lines.append(
            f"4. The deployed stack includes an automatic token rotation "
            f"Lambda that refreshes the access token on the schedule "
            f"`{oauth.refresh_schedule_expression}` using the token endpoint "
            f"`{oauth.token_endpoint_url}`.",
        )
        lines.append("")
