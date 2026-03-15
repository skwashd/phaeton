"""Tests for the SSM parameter writer."""

from __future__ import annotations

from n8n_to_sfn_packager.models.inputs import CredentialSpec, OAuthCredentialSpec
from n8n_to_sfn_packager.writers.ssm_writer import _CREDENTIAL_DOCS, SSMWriter


def _make_standard_cred() -> CredentialSpec:
    return CredentialSpec(
        parameter_path="/my-workflow/credentials/slack_token",
        description="Slack Bot Token",
        credential_type="apiKey",
        placeholder_value="<your-slack-bot-token>",
        associated_node_names=["Slack"],
    )


def _make_oauth_cred() -> OAuthCredentialSpec:
    return OAuthCredentialSpec(
        credential_spec=CredentialSpec(
            parameter_path="/my-workflow/credentials/google_oauth",
            description="Google OAuth",
            credential_type="oauth2",
            associated_node_names=["Google Sheets"],
        ),
        token_endpoint_url="https://oauth2.googleapis.com/token",  # noqa: S106
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )


class TestStandardCredentials:
    """Tests for standard credential SSM parameter generation."""

    def test_generates_one_parameter(self) -> None:
        """Test that one standard credential generates one parameter."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert len(params) == 1

    def test_correct_path(self) -> None:
        """Test that the parameter path matches the credential path."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert params[0].parameter_path == "/my-workflow/credentials/slack_token"

    def test_placeholder_value(self) -> None:
        """Test that the placeholder value is preserved."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert params[0].placeholder_value == "<your-slack-bot-token>"

    def test_parameter_type_is_secure_string(self) -> None:
        """Test that the parameter type is SecureString."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert params[0].parameter_type == "SecureString"

    def test_default_placeholder_when_empty(self) -> None:
        """Test that a default placeholder is generated when none provided."""
        writer = SSMWriter()
        cred = CredentialSpec(
            parameter_path="/workflow/creds/api",
            credential_type="apiKey",
            associated_node_names=["HTTP Request"],
        )
        params = writer.generate_parameter_definitions([cred], [])
        assert "<your-apiKey-credential>" in params[0].placeholder_value


class TestOAuthCredentials:
    """Tests for OAuth credential SSM parameter generation."""

    def test_generates_two_parameters(self) -> None:
        """Test that one OAuth credential generates two parameters."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        assert len(params) == 2

    def test_access_token_path(self) -> None:
        """Test that access token parameter path is correct."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        paths = [p.parameter_path for p in params]
        assert "/my-workflow/credentials/google_oauth/access_token" in paths

    def test_refresh_token_path(self) -> None:
        """Test that refresh token parameter path is correct."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        paths = [p.parameter_path for p in params]
        assert "/my-workflow/credentials/google_oauth/refresh_token" in paths

    def test_access_token_placeholder(self) -> None:
        """Test that access token placeholder is correct."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        access = next(p for p in params if "access_token" in p.parameter_path)
        assert access.placeholder_value == "<oauth2-access-token>"

    def test_refresh_token_placeholder(self) -> None:
        """Test that refresh token placeholder is correct."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        refresh = next(p for p in params if "refresh_token" in p.parameter_path)
        assert refresh.placeholder_value == "<oauth2-refresh-token>"


class TestMixedCredentials:
    """Tests for mixed credential SSM parameter generation."""

    def test_combined_output(self) -> None:
        """Test that mixed credentials produce the correct total count."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions(
            [_make_standard_cred()],
            [_make_oauth_cred()],
        )
        # 1 standard + 2 oauth = 3 total
        assert len(params) == 3

    def test_path_naming_convention(self) -> None:
        """Test that all parameter paths start with a leading slash."""
        writer = SSMWriter()
        params = writer.generate_parameter_definitions(
            [_make_standard_cred()],
            [_make_oauth_cred()],
        )
        for param in params:
            assert param.parameter_path.startswith("/")


class TestCredentialDocumentationStandard:
    """Tests for credential documentation with standard credentials."""

    def test_contains_parameter_path(self) -> None:
        """Test that the SSM parameter path appears in the documentation."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([_make_standard_cred()], [])
        assert "/my-workflow/credentials/slack_token" in doc

    def test_contains_credential_type(self) -> None:
        """Test that the credential type appears in the documentation."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([_make_standard_cred()], [])
        assert "apiKey" in doc

    def test_contains_placeholder_warning(self) -> None:
        """Test that a placeholder warning is prominently displayed."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([_make_standard_cred()], [])
        assert "WARNING" in doc
        assert "will fail" in doc
        assert "placeholder" in doc.lower()

    def test_contains_aws_cli_instructions(self) -> None:
        """Test that AWS CLI put-parameter instructions are included."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([_make_standard_cred()], [])
        assert "aws ssm put-parameter" in doc

    def test_contains_associated_nodes(self) -> None:
        """Test that associated node names are listed."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([_make_standard_cred()], [])
        assert "Slack" in doc

    def test_contains_description(self) -> None:
        """Test that the credential description is used as section header."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([_make_standard_cred()], [])
        assert "Slack Bot Token" in doc

    def test_known_service_docs_url(self) -> None:
        """Test that a known credential type gets a documentation link."""
        writer = SSMWriter()
        cred = CredentialSpec(
            parameter_path="/wf/creds/slack",
            credential_type="slackApi",
            associated_node_names=["Slack"],
        )
        doc = writer.generate_credential_documentation([cred], [])
        assert _CREDENTIAL_DOCS["slack"] in doc


class TestCredentialDocumentationOAuth:
    """Tests for credential documentation with OAuth credentials."""

    def test_contains_access_token_path(self) -> None:
        """Test that the access token SSM path appears."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [_make_oauth_cred()])
        assert "/my-workflow/credentials/google_oauth/access_token" in doc

    def test_contains_refresh_token_path(self) -> None:
        """Test that the refresh token SSM path appears."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [_make_oauth_cred()])
        assert "/my-workflow/credentials/google_oauth/refresh_token" in doc

    def test_contains_token_endpoint(self) -> None:
        """Test that the token endpoint URL appears."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [_make_oauth_cred()])
        assert "https://oauth2.googleapis.com/token" in doc

    def test_contains_refresh_schedule(self) -> None:
        """Test that the refresh schedule expression appears."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [_make_oauth_cred()])
        assert "rate(50 minutes)" in doc

    def test_contains_scopes(self) -> None:
        """Test that OAuth scopes appear in the documentation."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [_make_oauth_cred()])
        assert "spreadsheets" in doc

    def test_contains_oauth_setup_instructions(self) -> None:
        """Test that OAuth-specific setup steps are included."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [_make_oauth_cred()])
        assert "client ID" in doc
        assert "authorization flow" in doc
        assert "token rotation" in doc.lower()


class TestCredentialDocumentationEmpty:
    """Tests for credential documentation with no credentials."""

    def test_no_credentials_produces_minimal_doc(self) -> None:
        """Test that no credentials produces a document stating none are needed."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [])
        assert "does not require any credentials" in doc

    def test_no_credentials_still_has_title(self) -> None:
        """Test that the no-credentials document still has a title."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [])
        assert "# Credential Setup Guide" in doc

    def test_no_credentials_still_has_warning(self) -> None:
        """Test that the placeholder warning appears even with no credentials."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation([], [])
        assert "WARNING" in doc


class TestCredentialDocumentationMixed:
    """Tests for credential documentation with mixed credentials."""

    def test_all_parameter_paths_present(self) -> None:
        """Test that all SSM parameter paths appear in the documentation."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation(
            [_make_standard_cred()],
            [_make_oauth_cred()],
        )
        assert "/my-workflow/credentials/slack_token" in doc
        assert "/my-workflow/credentials/google_oauth/access_token" in doc
        assert "/my-workflow/credentials/google_oauth/refresh_token" in doc

    def test_has_both_sections(self) -> None:
        """Test that both standard and OAuth sections are present."""
        writer = SSMWriter()
        doc = writer.generate_credential_documentation(
            [_make_standard_cred()],
            [_make_oauth_cred()],
        )
        assert "## Standard Credentials" in doc
        assert "## OAuth Credentials" in doc
