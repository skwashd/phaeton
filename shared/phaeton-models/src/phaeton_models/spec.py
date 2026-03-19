"""
API spec boundary models shared across Phaeton components.

Defines the contract types for the spec index JSON that is written to and
read from S3: ``SpecEndpoint``, ``ApiSpecEntry``, ``ApiSpecIndex``, and
``NodeApiMapping``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
