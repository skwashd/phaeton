"""Aurora RDS Data API database node translator.

Converts database nodes classified as ``AWS_NATIVE`` into Step Functions
``aws-sdk:rdsdata:executeStatement`` and ``aws-sdk:rdsdata:batchExecuteStatement``
Task states using the RDS Data API (HTTP API).
"""

from __future__ import annotations

from typing import Any

from phaeton_models.translator import ClassifiedNode, NodeClassification

from n8n_to_sfn.models.asl import RetryConfig, TaskState
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    CredentialArtifact,
    TranslationContext,
    TranslationResult,
    apply_error_handling,
)

_DATABASE_NODE_TYPE = "n8n-nodes-base.postgres"

_EXECUTE_RESOURCE = "arn:aws:states:::aws-sdk:rdsdata:executeStatement"
_BATCH_RESOURCE = "arn:aws:states:::aws-sdk:rdsdata:batchExecuteStatement"

_DEFAULT_RETRY = RetryConfig(
    error_equals=["States.TaskFailed"],
    interval_seconds=2,
    max_attempts=3,
    backoff_rate=2.0,
    max_delay_seconds=30,
)

_SUPPORTED_DB_NODE_TYPES = frozenset({
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mySql",
    "n8n-nodes-base.microsoftSql",
})


def _build_ssm_path(workflow_name: str, credential_type: str) -> str:
    """Build the SSM parameter path for a credential."""
    safe_name = workflow_name.replace(" ", "-").lower() if workflow_name else "workflow"
    return f"/n8n-sfn/{safe_name}/{credential_type}"


def _build_select_sql(params: dict[str, Any]) -> str:
    """Build a SELECT SQL statement from ORM-style parameters.

    These SQL templates are not executed directly — they are passed to the
    RDS Data API ``ExecuteStatement`` action, which handles parameterized
    values separately via the ``Parameters`` field.
    """
    table = params.get("table", "")
    columns = params.get("columns", "*")
    where = params.get("where", "")
    limit = params.get("limit", "")
    sort = params.get("sort", "")

    parts = ["SELECT", columns, "FROM", table]
    if where:
        parts.extend(["WHERE", where])
    if sort:
        parts.extend(["ORDER BY", sort])
    if limit:
        parts.extend(["LIMIT", limit])
    return " ".join(parts)


def _build_insert_sql(params: dict[str, Any]) -> str:
    """Build an INSERT SQL statement from ORM-style parameters.

    SQL template only — actual values are parameterized via RDS Data API.
    """
    table = params.get("table", "")
    columns_str = params.get("columns", "")
    values_str = params.get("values", "")
    parts = ["INSERT INTO", table]
    parts.append("(" + columns_str + ")")
    parts.append("VALUES")
    parts.append("(" + values_str + ")")
    return " ".join(parts)


def _build_update_sql(params: dict[str, Any]) -> str:
    """Build an UPDATE SQL statement from ORM-style parameters.

    SQL template only — actual values are parameterized via RDS Data API.
    """
    table = params.get("table", "")
    set_clause = params.get("set", "")
    where = params.get("where", "")

    parts = ["UPDATE", table, "SET", set_clause]
    if where:
        parts.extend(["WHERE", where])
    return " ".join(parts)


def _build_delete_sql(params: dict[str, Any]) -> str:
    """Build a DELETE SQL statement from ORM-style parameters.

    SQL template only — actual values are parameterized via RDS Data API.
    """
    table = params.get("table", "")
    where = params.get("where", "")

    parts = ["DELETE FROM", table]
    if where:
        parts.extend(["WHERE", where])
    return " ".join(parts)


_OPERATION_BUILDERS: dict[str, Any] = {
    "select": _build_select_sql,
    "insert": _build_insert_sql,
    "update": _build_update_sql,
    "delete": _build_delete_sql,
}


class DatabaseTranslator(BaseTranslator):
    """Translates database nodes into RDS Data API Task states."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True for database nodes classified as AWS_NATIVE."""
        return (
            node.node.type in _SUPPORTED_DB_NODE_TYPES
            and node.classification == NodeClassification.AWS_NATIVE
        )

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a database node into an RDS Data API Task state."""
        params = node.node.parameters
        warnings: list[str] = []

        sql = self._resolve_sql(params, warnings, node.node.name)
        is_batch = bool(params.get("batch", False))

        resource = _BATCH_RESOURCE if is_batch else _EXECUTE_RESOURCE

        arguments: dict[str, Any] = {
            "ResourceArn": "${DatabaseClusterArn}",
            "SecretArn": "${DatabaseSecretArn}",
            "Database": "${DatabaseName}",
            "Sql": sql,
        }

        sql_parameters = params.get("parameters")
        if sql_parameters:
            if is_batch:
                arguments["ParameterSets"] = sql_parameters
            else:
                arguments["Parameters"] = sql_parameters

        credential_artifacts = self._build_credentials(context)

        state = TaskState(
            resource=resource,
            arguments=arguments,
            end=True,
            retry=[_DEFAULT_RETRY],
        )
        state = apply_error_handling(state, node, default_retry=_DEFAULT_RETRY)

        return TranslationResult(
            states={node.node.name: state},
            credential_artifacts=credential_artifacts,
            warnings=warnings,
        )

    @staticmethod
    def _resolve_sql(
        params: dict[str, Any],
        warnings: list[str],
        node_name: str,
    ) -> str:
        """Resolve the SQL query from node parameters."""
        raw_query = params.get("query")
        if raw_query:
            return str(raw_query)

        operation = str(params.get("operation", "select")).lower()
        builder = _OPERATION_BUILDERS.get(operation)
        if builder is None:
            warnings.append(
                f"Unsupported database operation '{operation}' for node "
                f"'{node_name}'. Defaulting to empty query."
            )
            return ""
        return builder(params)

    @staticmethod
    def _build_credentials(
        context: TranslationContext,
    ) -> list[CredentialArtifact]:
        """Build credential artifacts for database connection secrets."""
        ssm_path = _build_ssm_path(context.workflow_name, "databaseSecret")
        return [
            CredentialArtifact(
                parameter_path=ssm_path,
                credential_type="databaseSecret",
                auth_type="secret_arn",
                placeholder_value="<your-database-secret-arn>",
            ),
        ]
