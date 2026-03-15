"""
Pydantic models for all data structures used in the n8n release parser.

Defines the core node catalog models, diff models, API spec matching models,
and priority classification enums. All value objects use frozen model config
for immutability.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Core node catalog models
# ---------------------------------------------------------------------------


class NodeParameter(BaseModel):
    """A single parameter from an n8n INodeTypeDescription properties array."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    type: str
    default: Any = None
    required: bool = False
    options: list[dict[str, Any]] | None = None
    has_expressions: bool = False
    display_options: dict[str, Any] | None = None
    description: str = ""


class CredentialType(BaseModel):
    """A credential reference within a node type description."""

    model_config = ConfigDict(frozen=True)

    name: str
    required: bool = True


class ResourceOperation(BaseModel):
    """A resource/operation pair (e.g. message:send)."""

    model_config = ConfigDict(frozen=True)

    resource: str
    operation: str
    description: str = ""


class NodeTypeEntry(BaseModel):
    """A single node type entry in the versioned catalog."""

    model_config = ConfigDict(frozen=True)

    node_type: str
    type_version: int
    display_name: str
    description: str = ""
    group: list[str] = []
    parameters: list[NodeParameter] = []
    credential_types: list[CredentialType] = []
    resource_operations: list[ResourceOperation] = []
    input_count: int = 1
    output_count: int = 1
    default_values: dict[str, Any] = {}
    request_defaults: dict[str, Any] | None = None
    source_n8n_version: str = ""


class NodeCatalog(BaseModel):
    """The full node catalog for a specific n8n release."""

    model_config = ConfigDict(frozen=True)

    n8n_version: str
    release_date: datetime
    entries: list[NodeTypeEntry] = []
    parse_timestamp: datetime | None = None
    parser_version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Diff models
# ---------------------------------------------------------------------------


class ChangeType(enum.StrEnum):
    """Type of change detected between releases."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class NodeChange(BaseModel):
    """Describes a change to a node between two releases."""

    model_config = ConfigDict(frozen=True)

    node_type: str
    change_type: ChangeType
    old_version: NodeTypeEntry | None = None
    new_version: NodeTypeEntry | None = None
    changed_fields: list[str] = []


class ReleaseDiff(BaseModel):
    """Diff between two n8n releases."""

    model_config = ConfigDict(frozen=True)

    from_version: str
    to_version: str
    changes: list[NodeChange] = []
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0


# ---------------------------------------------------------------------------
# API spec matching models
# ---------------------------------------------------------------------------


class SpecEndpoint(BaseModel):
    """An endpoint extracted from an API spec."""

    model_config = ConfigDict(frozen=True)

    resource: str
    operation: str
    endpoint: str


class ApiSpecEntry(BaseModel):
    """An indexed API spec file."""

    model_config = ConfigDict(frozen=True)

    spec_filename: str
    service_name: str
    base_urls: list[str] = []
    auth_type: str = "none"
    spec_format: str = "openapi3"
    endpoints: list[SpecEndpoint] = []


class ApiSpecIndex(BaseModel):
    """The full API spec index."""

    model_config = ConfigDict(frozen=True)

    entries: list[ApiSpecEntry] = []
    index_timestamp: datetime | None = None


class NodeApiMapping(BaseModel):
    """Maps an n8n node to an API spec with operation-level mappings."""

    model_config = ConfigDict(frozen=True)

    node_type: str
    type_version: int
    api_spec: str
    spec_format: str
    operation_mappings: dict[str, str] = {}
    credential_type: str = ""
    auth_type: str = ""
    unmapped_operations: list[str] = []
    spec_coverage: float = 0.0

    def to_plan_json(self) -> dict[str, object]:
        """Serialize to the JSON format defined in the architecture plan."""
        return {
            "nodeType": self.node_type,
            "typeVersion": self.type_version,
            "apiSpec": self.api_spec,
            "specFormat": self.spec_format,
            "operationMappings": dict(self.operation_mappings),
            "credentialType": self.credential_type,
            "authType": self.auth_type,
            "unmappedOperations": list(self.unmapped_operations),
            "specCoverage": self.spec_coverage,
        }


# ---------------------------------------------------------------------------
# Priority classification
# ---------------------------------------------------------------------------


class NodeClassification(enum.StrEnum):
    """Classification of an n8n node for translation strategy."""

    AWS_NATIVE = "AWS_NATIVE"
    FLOW_CONTROL = "FLOW_CONTROL"
    TRIGGER = "TRIGGER"
    PICOFUN_API = "PICOFUN_API"
    GRAPHQL_API = "GRAPHQL_API"
    CODE_JS = "CODE_JS"
    CODE_PYTHON = "CODE_PYTHON"
    UNSUPPORTED = "UNSUPPORTED"


# ---------------------------------------------------------------------------
# npm version info (used by fetcher)
# ---------------------------------------------------------------------------


class NpmVersionInfo(BaseModel):
    """Version metadata from the npm registry."""

    model_config = ConfigDict(frozen=True)

    version: str
    publish_date: datetime
    tarball_url: str
