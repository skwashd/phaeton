"""SSM Parameter Store writer.

Generates SSM parameter definitions from credential and OAuth credential
specs for inclusion in the CDK stack.
"""

from __future__ import annotations

from n8n_to_sfn_packager.models.inputs import CredentialSpec, OAuthCredentialSpec
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition


class SSMWriter:
    """Generates SSM parameter definitions from credential specs."""

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
