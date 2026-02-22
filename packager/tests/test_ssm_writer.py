"""Tests for the SSM parameter writer."""

from __future__ import annotations

from n8n_to_sfn_packager.models.inputs import CredentialSpec, OAuthCredentialSpec
from n8n_to_sfn_packager.writers.ssm_writer import SSMWriter


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
        token_endpoint_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )


class TestStandardCredentials:
    def test_generates_one_parameter(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert len(params) == 1

    def test_correct_path(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert params[0].parameter_path == "/my-workflow/credentials/slack_token"

    def test_placeholder_value(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert params[0].placeholder_value == "<your-slack-bot-token>"

    def test_parameter_type_is_secure_string(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([_make_standard_cred()], [])
        assert params[0].parameter_type == "SecureString"

    def test_default_placeholder_when_empty(self):
        writer = SSMWriter()
        cred = CredentialSpec(
            parameter_path="/workflow/creds/api",
            credential_type="apiKey",
            associated_node_names=["HTTP Request"],
        )
        params = writer.generate_parameter_definitions([cred], [])
        assert "<your-apiKey-credential>" in params[0].placeholder_value


class TestOAuthCredentials:
    def test_generates_two_parameters(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        assert len(params) == 2

    def test_access_token_path(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        paths = [p.parameter_path for p in params]
        assert "/my-workflow/credentials/google_oauth/access_token" in paths

    def test_refresh_token_path(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        paths = [p.parameter_path for p in params]
        assert "/my-workflow/credentials/google_oauth/refresh_token" in paths

    def test_access_token_placeholder(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        access = next(p for p in params if "access_token" in p.parameter_path)
        assert access.placeholder_value == "<oauth2-access-token>"

    def test_refresh_token_placeholder(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions([], [_make_oauth_cred()])
        refresh = next(p for p in params if "refresh_token" in p.parameter_path)
        assert refresh.placeholder_value == "<oauth2-refresh-token>"


class TestMixedCredentials:
    def test_combined_output(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions(
            [_make_standard_cred()],
            [_make_oauth_cred()],
        )
        # 1 standard + 2 oauth = 3 total
        assert len(params) == 3

    def test_path_naming_convention(self):
        writer = SSMWriter()
        params = writer.generate_parameter_definitions(
            [_make_standard_cred()],
            [_make_oauth_cred()],
        )
        for param in params:
            assert param.parameter_path.startswith("/")
