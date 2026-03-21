"""Tests for Aurora RDS Data API database node translator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.database import DatabaseTranslator


def _db_node(
    name: str = "Database Query",
    params: dict | None = None,
    credentials: dict | None = None,
    node_type: str = "n8n-nodes-base.postgres",
    classification: NodeClassification = NodeClassification.AWS_NATIVE,
) -> ClassifiedNode:
    """Create a database classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
            parameters=params or {},
            credentials=credentials,
        ),
        classification=classification,
    )


def _context(workflow_name: str = "test-workflow") -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name=workflow_name,
    )


class TestDatabaseTranslatorCanTranslate:
    """Tests for can_translate routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_can_translate_postgres_aws_native(self) -> None:
        """Test can_translate returns True for postgres nodes classified as AWS_NATIVE."""
        node = _db_node()
        assert self.translator.can_translate(node)

    def test_can_translate_mysql_aws_native(self) -> None:
        """Test can_translate returns True for MySQL nodes classified as AWS_NATIVE."""
        node = _db_node(node_type="n8n-nodes-base.mySql")
        assert self.translator.can_translate(node)

    def test_can_translate_mssql_aws_native(self) -> None:
        """Test can_translate returns True for MSSQL nodes classified as AWS_NATIVE."""
        node = _db_node(node_type="n8n-nodes-base.microsoftSql")
        assert self.translator.can_translate(node)

    def test_cannot_translate_non_aws_native(self) -> None:
        """Test can_translate returns False for non-AWS_NATIVE classification."""
        node = _db_node(classification=NodeClassification.PICOFUN_API)
        assert not self.translator.can_translate(node)

    def test_cannot_translate_other_node_type(self) -> None:
        """Test can_translate returns False for non-database node types."""
        node = ClassifiedNode(
            node=N8nNode(
                id="x",
                name="x",
                type="n8n-nodes-base.httpRequest",
                type_version=1,
                position=[0, 0],
            ),
            classification=NodeClassification.AWS_NATIVE,
        )
        assert not self.translator.can_translate(node)


class TestSelectQuery:
    """Tests for SELECT query translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_raw_select_query(self) -> None:
        """Test raw SQL SELECT query translation."""
        node = _db_node(
            params={
                "query": "SELECT * FROM users WHERE id = :id",
            }
        )
        result = self.translator.translate(node, _context())

        assert "Database Query" in result.states
        state = result.states["Database Query"]
        assert state.resource == "arn:aws:states:::aws-sdk:rdsdata:executeStatement"
        assert state.arguments is not None
        assert state.arguments["Sql"] == "SELECT * FROM users WHERE id = :id"

    def test_select_with_parameters(self) -> None:
        """Test SELECT query with parameterized values."""
        node = _db_node(
            params={
                "query": "SELECT * FROM users WHERE id = :id",
                "parameters": [
                    {
                        "name": "id",
                        "value": {"longValue": "{% $states.input.userId %}"},
                    },
                ],
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["Parameters"] == [
            {"name": "id", "value": {"longValue": "{% $states.input.userId %}"}},
        ]

    def test_orm_style_select(self) -> None:
        """Test ORM-style SELECT operation builds SQL from parameters."""
        node = _db_node(
            params={
                "operation": "select",
                "table": "users",
                "columns": "id, name, email",
                "where": "active = true",
                "sort": "name ASC",
                "limit": "10",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        expected = "SELECT id, name, email FROM users WHERE active = true ORDER BY name ASC LIMIT 10"
        assert state.arguments["Sql"] == expected

    def test_orm_select_defaults(self) -> None:
        """Test ORM-style SELECT with default columns (*)."""
        node = _db_node(
            params={
                "operation": "select",
                "table": "users",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["Sql"] == "SELECT * FROM users"


class TestInsertQuery:
    """Tests for INSERT query translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_raw_insert_query(self) -> None:
        """Test raw SQL INSERT query translation."""
        node = _db_node(
            params={
                "query": "INSERT INTO users (name, email) VALUES (:name, :email)",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert (
            state.arguments["Sql"]
            == "INSERT INTO users (name, email) VALUES (:name, :email)"
        )

    def test_orm_style_insert(self) -> None:
        """Test ORM-style INSERT operation builds SQL from parameters."""
        node = _db_node(
            params={
                "operation": "insert",
                "table": "users",
                "columns": "name, email",
                "values": ":name, :email",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert (
            state.arguments["Sql"]
            == "INSERT INTO users (name, email) VALUES (:name, :email)"
        )


class TestUpdateQuery:
    """Tests for UPDATE query translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_raw_update_query(self) -> None:
        """Test raw SQL UPDATE query translation."""
        node = _db_node(
            params={
                "query": "UPDATE users SET name = :name WHERE id = :id",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["Sql"] == "UPDATE users SET name = :name WHERE id = :id"

    def test_orm_style_update(self) -> None:
        """Test ORM-style UPDATE operation builds SQL from parameters."""
        node = _db_node(
            params={
                "operation": "update",
                "table": "users",
                "set": "name = :name, email = :email",
                "where": "id = :id",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert (
            state.arguments["Sql"]
            == "UPDATE users SET name = :name, email = :email WHERE id = :id"
        )


class TestDeleteQuery:
    """Tests for DELETE query translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_raw_delete_query(self) -> None:
        """Test raw SQL DELETE query translation."""
        node = _db_node(
            params={
                "query": "DELETE FROM users WHERE id = :id",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["Sql"] == "DELETE FROM users WHERE id = :id"

    def test_orm_style_delete(self) -> None:
        """Test ORM-style DELETE operation builds SQL from parameters."""
        node = _db_node(
            params={
                "operation": "delete",
                "table": "users",
                "where": "id = :id",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["Sql"] == "DELETE FROM users WHERE id = :id"


class TestBatchStatements:
    """Tests for batch statement generation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_batch_uses_batch_resource(self) -> None:
        """Test batch operations use batchExecuteStatement resource."""
        node = _db_node(
            params={
                "query": "INSERT INTO users (name) VALUES (:name)",
                "batch": True,
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert (
            state.resource == "arn:aws:states:::aws-sdk:rdsdata:batchExecuteStatement"
        )

    def test_batch_with_parameter_sets(self) -> None:
        """Test batch operations map parameters to ParameterSets."""
        parameter_sets = [
            [{"name": "name", "value": {"stringValue": "Alice"}}],
            [{"name": "name", "value": {"stringValue": "Bob"}}],
        ]
        node = _db_node(
            params={
                "query": "INSERT INTO users (name) VALUES (:name)",
                "batch": True,
                "parameters": parameter_sets,
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["ParameterSets"] == parameter_sets
        assert "Parameters" not in state.arguments

    def test_non_batch_uses_execute_resource(self) -> None:
        """Test non-batch operations use executeStatement resource."""
        node = _db_node(
            params={
                "query": "SELECT 1",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.resource == "arn:aws:states:::aws-sdk:rdsdata:executeStatement"


class TestConnectionParameters:
    """Tests for database connection parameterization."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_cluster_arn_parameterized(self) -> None:
        """Test ResourceArn uses parameterized placeholder."""
        node = _db_node(params={"query": "SELECT 1"})
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["ResourceArn"] == "${DatabaseClusterArn}"

    def test_secret_arn_parameterized(self) -> None:
        """Test SecretArn uses parameterized placeholder."""
        node = _db_node(params={"query": "SELECT 1"})
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["SecretArn"] == "${DatabaseSecretArn}"

    def test_database_name_parameterized(self) -> None:
        """Test Database uses parameterized placeholder."""
        node = _db_node(params={"query": "SELECT 1"})
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.arguments is not None
        assert state.arguments["Database"] == "${DatabaseName}"


class TestCredentialArtifacts:
    """Tests for credential artifact generation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_credential_artifact_created(self) -> None:
        """Test credential artifact is created for database secret."""
        node = _db_node(params={"query": "SELECT 1"})
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "databaseSecret"
        assert cred.auth_type == "secret_arn"
        assert cred.placeholder_value == "<your-database-secret-arn>"

    def test_ssm_path_convention(self) -> None:
        """Test SSM path follows project convention."""
        node = _db_node(params={"query": "SELECT 1"})
        result = self.translator.translate(node, _context("My Workflow"))

        cred = result.credential_artifacts[0]
        assert cred.parameter_path == "/n8n-sfn/my-workflow/databaseSecret"


class TestRetryAndErrorHandling:
    """Tests for default retry and error handling."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_default_retry_present(self) -> None:
        """Test default retry configuration is present."""
        node = _db_node(params={"query": "SELECT 1"})
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        assert state.retry is not None
        assert len(state.retry) > 0
        assert state.retry[0].error_equals == ["States.TaskFailed"]


class TestAslValidity:
    """Tests for generated ASL validity."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = DatabaseTranslator()

    def test_serialized_state_has_required_fields(self) -> None:
        """Test that serialized state contains required ASL fields."""
        node = _db_node(
            params={
                "query": "SELECT * FROM users",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Task"
        assert (
            serialized["Resource"]
            == "arn:aws:states:::aws-sdk:rdsdata:executeStatement"
        )
        assert "Arguments" in serialized
        assert serialized["Arguments"]["Sql"] == "SELECT * FROM users"
        assert serialized["Arguments"]["ResourceArn"] == "${DatabaseClusterArn}"
        assert serialized["Arguments"]["SecretArn"] == "${DatabaseSecretArn}"
        assert serialized["Arguments"]["Database"] == "${DatabaseName}"

    def test_batch_serialized_state(self) -> None:
        """Test that serialized batch state uses correct resource."""
        node = _db_node(
            params={
                "query": "INSERT INTO users (name) VALUES (:name)",
                "batch": True,
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["Database Query"]
        serialized = state.model_dump(by_alias=True)
        assert (
            serialized["Resource"]
            == "arn:aws:states:::aws-sdk:rdsdata:batchExecuteStatement"
        )

    def test_unsupported_operation_warning(self) -> None:
        """Test that unsupported operations produce a warning."""
        node = _db_node(
            params={
                "operation": "upsert",
                "table": "users",
            }
        )
        result = self.translator.translate(node, _context())

        assert len(result.warnings) == 1
        assert "Unsupported database operation" in result.warnings[0]
        assert "upsert" in result.warnings[0]
