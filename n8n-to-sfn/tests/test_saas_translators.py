"""Tests for SaaS integration node translators."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.saas.airtable import AirtableTranslator
from n8n_to_sfn.translators.saas.gmail import GmailTranslator
from n8n_to_sfn.translators.saas.google_sheets import GoogleSheetsTranslator
from n8n_to_sfn.translators.saas.notion import NotionTranslator
from n8n_to_sfn.translators.saas.slack import SlackTranslator


def _saas_node(
    name: str = "SaaS Node",
    node_type: str = "n8n-nodes-base.slack",
    params: dict | None = None,
    credentials: dict | None = None,
) -> ClassifiedNode:
    """Create a SaaS classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id=name,
            name=name,
            type=node_type,
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters=params or {},
            credentials=credentials,
        ),
        classification=NodeClassification.PICOFUN_API,
    )


def _context(workflow_name: str = "test-workflow") -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name=workflow_name,
    )


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


class TestSlackCanTranslate:
    """Tests for Slack translator routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SlackTranslator()

    def test_can_translate_slack(self) -> None:
        """Test can_translate returns True for Slack nodes."""
        node = _saas_node(node_type="n8n-nodes-base.slack")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-Slack nodes."""
        node = _saas_node(node_type="n8n-nodes-base.gmail")
        assert not self.translator.can_translate(node)


class TestSlackMessagePost:
    """Tests for Slack message:post operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SlackTranslator()

    def test_post_message(self) -> None:
        """Test posting a Slack message produces correct API call."""
        node = _saas_node(
            name="Post Slack Message",
            node_type="n8n-nodes-base.slack",
            params={
                "resource": "message",
                "operation": "post",
                "channel": "C12345",
                "text": "Hello from Step Functions!",
            },
        )
        result = self.translator.translate(node, _context())

        assert "Post Slack Message" in result.states
        state = result.states["Post Slack Message"]
        assert state.resource == "arn:aws:states:::http:invoke"
        assert state.arguments is not None
        assert state.arguments["ApiEndpoint"] == "https://slack.com/api/chat.postMessage"
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"]["channel"] == "C12345"
        assert state.arguments["RequestBody"]["text"] == "Hello from Step Functions!"

    def test_post_message_credential_artifact(self) -> None:
        """Test posting a message creates OAuth2 credential artifact."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "message", "operation": "post", "channel": "C1", "text": "hi"},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "slackOAuth2Api"
        assert cred.auth_type == "oauth2"
        assert cred.parameter_path == "/n8n-sfn/test-workflow/slackOAuth2Api"

    def test_post_message_with_blocks(self) -> None:
        """Test posting a message with blocks passes them through."""
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "hello"}}]
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={
                "resource": "message",
                "operation": "post",
                "channel": "C1",
                "text": "hi",
                "blocks": blocks,
            },
        )
        result = self.translator.translate(node, _context())

        assert result.states["SaaS Node"].arguments["RequestBody"]["blocks"] == blocks


class TestSlackMessageUpdate:
    """Tests for Slack message:update operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SlackTranslator()

    def test_update_message(self) -> None:
        """Test updating a Slack message."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={
                "resource": "message",
                "operation": "update",
                "channel": "C12345",
                "ts": "1234567890.123456",
                "text": "Updated text",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["ApiEndpoint"] == "https://slack.com/api/chat.update"
        assert state.arguments["RequestBody"]["ts"] == "1234567890.123456"


class TestSlackChannelOperations:
    """Tests for Slack channel operations."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SlackTranslator()

    def test_get_channel(self) -> None:
        """Test getting a channel uses conversations.info endpoint."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "channel", "operation": "get"},
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["ApiEndpoint"] == "https://slack.com/api/conversations.info"
        assert state.arguments["Method"] == "GET"

    def test_get_all_channels(self) -> None:
        """Test listing channels uses conversations.list endpoint."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "channel", "operation": "getAll"},
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["ApiEndpoint"] == "https://slack.com/api/conversations.list"


class TestSlackUnsupportedOperation:
    """Tests for unsupported Slack operations."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SlackTranslator()

    def test_unsupported_operation_warning(self) -> None:
        """Test unsupported operation produces a warning."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "star", "operation": "add"},
        )
        result = self.translator.translate(node, _context())

        assert len(result.warnings) == 1
        assert "Unsupported operation" in result.warnings[0]
        assert "star:add" in result.warnings[0]


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------


class TestGmailCanTranslate:
    """Tests for Gmail translator routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GmailTranslator()

    def test_can_translate_gmail(self) -> None:
        """Test can_translate returns True for Gmail nodes."""
        node = _saas_node(node_type="n8n-nodes-base.gmail")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-Gmail nodes."""
        node = _saas_node(node_type="n8n-nodes-base.slack")
        assert not self.translator.can_translate(node)


class TestGmailMessageSend:
    """Tests for Gmail message:send operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GmailTranslator()

    def test_send_message(self) -> None:
        """Test sending a Gmail message produces correct API call."""
        node = _saas_node(
            name="Send Email",
            node_type="n8n-nodes-base.gmail",
            params={
                "resource": "message",
                "operation": "send",
                "to": "user@example.com",
                "subject": "Test Subject",
                "message": "Hello, World!",
            },
        )
        result = self.translator.translate(node, _context())

        assert "Send Email" in result.states
        state = result.states["Send Email"]
        assert state.arguments["ApiEndpoint"] == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        assert state.arguments["Method"] == "POST"
        assert "user@example.com" in state.arguments["RequestBody"]["raw"]
        assert "Test Subject" in state.arguments["RequestBody"]["raw"]

    def test_send_message_credential(self) -> None:
        """Test Gmail send creates OAuth2 credential artifact."""
        node = _saas_node(
            node_type="n8n-nodes-base.gmail",
            params={"resource": "message", "operation": "send", "to": "a@b.com", "subject": "s"},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "gmailOAuth2Api"
        assert cred.auth_type == "oauth2"


class TestGmailMessageGet:
    """Tests for Gmail message:get operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GmailTranslator()

    def test_get_message(self) -> None:
        """Test getting a Gmail message resolves messageId in endpoint."""
        node = _saas_node(
            node_type="n8n-nodes-base.gmail",
            params={
                "resource": "message",
                "operation": "get",
                "messageId": "abc123",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert "abc123" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "GET"

    def test_get_all_messages(self) -> None:
        """Test listing Gmail messages uses messages endpoint."""
        node = _saas_node(
            node_type="n8n-nodes-base.gmail",
            params={"resource": "message", "operation": "getAll"},
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["ApiEndpoint"].endswith("/messages")
        assert state.arguments["Method"] == "GET"


class TestGmailDraft:
    """Tests for Gmail draft operations."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GmailTranslator()

    def test_create_draft(self) -> None:
        """Test creating a draft produces correct body structure."""
        node = _saas_node(
            node_type="n8n-nodes-base.gmail",
            params={
                "resource": "draft",
                "operation": "create",
                "to": "user@example.com",
                "subject": "Draft Subject",
                "message": "Draft body",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert "message" in state.arguments["RequestBody"]
        assert "raw" in state.arguments["RequestBody"]["message"]


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------


class TestGoogleSheetsCanTranslate:
    """Tests for Google Sheets translator routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GoogleSheetsTranslator()

    def test_can_translate_sheets(self) -> None:
        """Test can_translate returns True for Google Sheets nodes."""
        node = _saas_node(node_type="n8n-nodes-base.googleSheets")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-Sheets nodes."""
        node = _saas_node(node_type="n8n-nodes-base.slack")
        assert not self.translator.can_translate(node)


class TestGoogleSheetsAppend:
    """Tests for Google Sheets append operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GoogleSheetsTranslator()

    def test_append_rows(self) -> None:
        """Test appending rows to a Google Sheet."""
        node = _saas_node(
            name="Append Rows",
            node_type="n8n-nodes-base.googleSheets",
            params={
                "resource": "sheet",
                "operation": "append",
                "spreadsheetId": "abc123",
                "range": "Sheet1!A1",
                "values": [["Name", "Email"], ["Alice", "alice@example.com"]],
            },
        )
        result = self.translator.translate(node, _context())

        assert "Append Rows" in result.states
        state = result.states["Append Rows"]
        assert "abc123" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"]["values"] == [
            ["Name", "Email"],
            ["Alice", "alice@example.com"],
        ]

    def test_sheets_credential(self) -> None:
        """Test Google Sheets creates OAuth2 credential artifact."""
        node = _saas_node(
            node_type="n8n-nodes-base.googleSheets",
            params={"resource": "sheet", "operation": "read", "spreadsheetId": "x", "range": "A1"},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "googleSheetsOAuth2Api"
        assert cred.auth_type == "oauth2"


class TestGoogleSheetsRead:
    """Tests for Google Sheets read operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GoogleSheetsTranslator()

    def test_read_sheet(self) -> None:
        """Test reading a Google Sheet range."""
        node = _saas_node(
            node_type="n8n-nodes-base.googleSheets",
            params={
                "resource": "sheet",
                "operation": "read",
                "spreadsheetId": "abc123",
                "range": "Sheet1!A1:D10",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert "abc123" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "GET"


class TestGoogleSheetsUpdate:
    """Tests for Google Sheets update operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GoogleSheetsTranslator()

    def test_update_sheet(self) -> None:
        """Test updating a Google Sheet range."""
        node = _saas_node(
            node_type="n8n-nodes-base.googleSheets",
            params={
                "resource": "sheet",
                "operation": "update",
                "spreadsheetId": "abc123",
                "range": "Sheet1!A1:B2",
                "values": [["Updated"]],
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["Method"] == "PUT"
        assert state.arguments["RequestBody"]["values"] == [["Updated"]]


class TestGoogleSheetsCreateSpreadsheet:
    """Tests for Google Sheets spreadsheet:create operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = GoogleSheetsTranslator()

    def test_create_spreadsheet(self) -> None:
        """Test creating a new spreadsheet."""
        node = _saas_node(
            node_type="n8n-nodes-base.googleSheets",
            params={
                "resource": "spreadsheet",
                "operation": "create",
                "title": "My New Sheet",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"]["properties"]["title"] == "My New Sheet"


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------


class TestNotionCanTranslate:
    """Tests for Notion translator routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = NotionTranslator()

    def test_can_translate_notion(self) -> None:
        """Test can_translate returns True for Notion nodes."""
        node = _saas_node(node_type="n8n-nodes-base.notion")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-Notion nodes."""
        node = _saas_node(node_type="n8n-nodes-base.slack")
        assert not self.translator.can_translate(node)


class TestNotionPageCreate:
    """Tests for Notion page:create operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = NotionTranslator()

    def test_create_page(self) -> None:
        """Test creating a Notion page produces correct API call."""
        properties = {"Name": {"title": [{"text": {"content": "Test Page"}}]}}
        node = _saas_node(
            name="Create Page",
            node_type="n8n-nodes-base.notion",
            params={
                "resource": "page",
                "operation": "create",
                "databaseId": "db-123",
                "properties": properties,
            },
        )
        result = self.translator.translate(node, _context())

        assert "Create Page" in result.states
        state = result.states["Create Page"]
        assert state.arguments["ApiEndpoint"] == "https://api.notion.com/v1/pages"
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"]["parent"]["database_id"] == "db-123"
        assert state.arguments["RequestBody"]["properties"] == properties

    def test_notion_credential(self) -> None:
        """Test Notion creates API key credential artifact."""
        node = _saas_node(
            node_type="n8n-nodes-base.notion",
            params={"resource": "page", "operation": "create", "databaseId": "x"},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "notionApi"
        assert cred.auth_type == "api_key"

    def test_notion_version_header(self) -> None:
        """Test Notion API version header is included."""
        node = _saas_node(
            node_type="n8n-nodes-base.notion",
            params={"resource": "page", "operation": "create", "databaseId": "x"},
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["Headers"]["Notion-Version"] == "2022-06-28"


class TestNotionDatabaseQuery:
    """Tests for Notion database:getAll (query) operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = NotionTranslator()

    def test_query_database(self) -> None:
        """Test querying a Notion database."""
        filter_obj = {"property": "Status", "select": {"equals": "Done"}}
        node = _saas_node(
            node_type="n8n-nodes-base.notion",
            params={
                "resource": "database",
                "operation": "getAll",
                "databaseId": "db-456",
                "filter": filter_obj,
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert "db-456" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"]["filter"] == filter_obj


class TestNotionSearch:
    """Tests for Notion search operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = NotionTranslator()

    def test_search_pages(self) -> None:
        """Test searching Notion pages."""
        node = _saas_node(
            node_type="n8n-nodes-base.notion",
            params={
                "resource": "search",
                "operation": "page",
                "text": "meeting notes",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["ApiEndpoint"] == "https://api.notion.com/v1/search"
        assert state.arguments["RequestBody"]["query"] == "meeting notes"


# ---------------------------------------------------------------------------
# Airtable
# ---------------------------------------------------------------------------


class TestAirtableCanTranslate:
    """Tests for Airtable translator routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = AirtableTranslator()

    def test_can_translate_airtable(self) -> None:
        """Test can_translate returns True for Airtable nodes."""
        node = _saas_node(node_type="n8n-nodes-base.airtable")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-Airtable nodes."""
        node = _saas_node(node_type="n8n-nodes-base.slack")
        assert not self.translator.can_translate(node)


class TestAirtableRecordCreate:
    """Tests for Airtable record:create operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = AirtableTranslator()

    def test_create_record(self) -> None:
        """Test creating an Airtable record produces correct API call."""
        fields = {"Name": "Alice", "Email": "alice@example.com"}
        node = _saas_node(
            name="Create Record",
            node_type="n8n-nodes-base.airtable",
            params={
                "resource": "record",
                "operation": "create",
                "baseId": "appXXX",
                "tableId": "tblYYY",
                "fields": fields,
            },
        )
        result = self.translator.translate(node, _context())

        assert "Create Record" in result.states
        state = result.states["Create Record"]
        assert "appXXX" in state.arguments["ApiEndpoint"]
        assert "tblYYY" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"]["fields"] == fields

    def test_airtable_credential(self) -> None:
        """Test Airtable creates API key credential artifact."""
        node = _saas_node(
            node_type="n8n-nodes-base.airtable",
            params={"resource": "record", "operation": "create", "baseId": "x", "tableId": "t"},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "airtableApi"
        assert cred.auth_type == "api_key"


class TestAirtableRecordGet:
    """Tests for Airtable record:get operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = AirtableTranslator()

    def test_get_record(self) -> None:
        """Test getting an Airtable record resolves recordId in endpoint."""
        node = _saas_node(
            node_type="n8n-nodes-base.airtable",
            params={
                "resource": "record",
                "operation": "get",
                "baseId": "appXXX",
                "tableId": "tblYYY",
                "recordId": "recZZZ",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert "recZZZ" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "GET"

    def test_get_all_records(self) -> None:
        """Test listing Airtable records."""
        node = _saas_node(
            node_type="n8n-nodes-base.airtable",
            params={
                "resource": "record",
                "operation": "getAll",
                "baseId": "appXXX",
                "tableId": "tblYYY",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["ApiEndpoint"].endswith("appXXX/tblYYY")
        assert state.arguments["Method"] == "GET"


class TestAirtableRecordUpdate:
    """Tests for Airtable record:update operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = AirtableTranslator()

    def test_update_record(self) -> None:
        """Test updating an Airtable record."""
        node = _saas_node(
            node_type="n8n-nodes-base.airtable",
            params={
                "resource": "record",
                "operation": "update",
                "baseId": "appXXX",
                "tableId": "tblYYY",
                "recordId": "recZZZ",
                "fields": {"Name": "Bob"},
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["Method"] == "PATCH"
        assert state.arguments["RequestBody"]["records"][0]["id"] == "recZZZ"
        assert state.arguments["RequestBody"]["records"][0]["fields"]["Name"] == "Bob"


class TestAirtableRecordDelete:
    """Tests for Airtable record:delete operation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = AirtableTranslator()

    def test_delete_record(self) -> None:
        """Test deleting an Airtable record."""
        node = _saas_node(
            node_type="n8n-nodes-base.airtable",
            params={
                "resource": "record",
                "operation": "delete",
                "baseId": "appXXX",
                "tableId": "tblYYY",
                "recordId": "recZZZ",
            },
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert "recZZZ" in state.arguments["ApiEndpoint"]
        assert state.arguments["Method"] == "DELETE"


# ---------------------------------------------------------------------------
# Common behavior (retry, error handling, ASL validity)
# ---------------------------------------------------------------------------


class TestRetryAndErrorHandling:
    """Tests for default retry configuration across SaaS translators."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translators = [
            ("n8n-nodes-base.slack", SlackTranslator()),
            ("n8n-nodes-base.gmail", GmailTranslator()),
            ("n8n-nodes-base.googleSheets", GoogleSheetsTranslator()),
            ("n8n-nodes-base.notion", NotionTranslator()),
            ("n8n-nodes-base.airtable", AirtableTranslator()),
        ]

    def test_default_retry_present(self) -> None:
        """Test default retry configuration is present for all SaaS translators."""
        for node_type, translator in self.translators:
            node = _saas_node(node_type=node_type, params={"resource": "x", "operation": "y"})
            result = translator.translate(node, _context())

            state = result.states["SaaS Node"]
            assert state.retry is not None, f"{node_type} missing retry"
            assert len(state.retry) > 0
            assert state.retry[0].error_equals == ["States.TaskFailed"]


class TestAslValidity:
    """Tests for generated ASL validity across SaaS translators."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SlackTranslator()

    def test_serialized_state_has_required_fields(self) -> None:
        """Test that serialized state contains required ASL fields."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "message", "operation": "post", "channel": "C1", "text": "hi"},
        )
        result = self.translator.translate(node, _context())

        state = result.states["SaaS Node"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Task"
        assert serialized["Resource"] == "arn:aws:states:::http:invoke"
        assert "Arguments" in serialized
        assert "ApiEndpoint" in serialized["Arguments"]
        assert "Method" in serialized["Arguments"]

    def test_ssm_path_convention(self) -> None:
        """Test SSM path follows project convention."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "message", "operation": "post"},
        )
        result = self.translator.translate(node, _context("My Workflow"))

        cred = result.credential_artifacts[0]
        assert cred.parameter_path == "/n8n-sfn/my-workflow/slackOAuth2Api"

    def test_metadata_includes_service_info(self) -> None:
        """Test metadata includes SaaS service and operation info."""
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "message", "operation": "post"},
        )
        result = self.translator.translate(node, _context())

        assert result.metadata["saas_service"] == "n8n-nodes-base.slack"
        assert result.metadata["operation"] == "message:post"


class TestAuthorizationHeaders:
    """Tests for authorization header construction."""

    def test_bearer_token_in_headers(self) -> None:
        """Test that Authorization Bearer header includes SSM path."""
        translator = SlackTranslator()
        node = _saas_node(
            node_type="n8n-nodes-base.slack",
            params={"resource": "message", "operation": "post"},
        )
        result = translator.translate(node, _context("my-wf"))

        state = result.states["SaaS Node"]
        auth_header = state.arguments["Headers"]["Authorization"]
        assert auth_header == "Bearer ${/n8n-sfn/my-wf/slackOAuth2Api}"

    def test_content_type_header(self) -> None:
        """Test that Content-Type header is set to application/json."""
        translator = AirtableTranslator()
        node = _saas_node(
            node_type="n8n-nodes-base.airtable",
            params={"resource": "record", "operation": "getAll", "baseId": "x", "tableId": "t"},
        )
        result = translator.translate(node, _context())

        state = result.states["SaaS Node"]
        assert state.arguments["Headers"]["Content-Type"] == "application/json"
