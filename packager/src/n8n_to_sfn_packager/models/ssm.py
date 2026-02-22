"""SSM Parameter Store models used by writers."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SSMParameterDefinition(BaseModel):
    """Definition for an SSM parameter to be created in the CDK stack."""

    parameter_path: str = Field(
        ...,
        description="Full SSM parameter path.",
    )
    description: str = Field(
        default="",
        description="Human-readable description.",
    )
    placeholder_value: str = Field(
        default="<placeholder>",
        description="Descriptive placeholder value for the parameter.",
    )
    parameter_type: str = Field(
        default="SecureString",
        description="SSM parameter type.",
    )
    kms_key_ref: str = Field(
        default="shared_kms_key",
        description="Reference to the KMS key for encryption.",
    )

    @field_validator("parameter_path")
    @classmethod
    def validate_parameter_path(cls, v: str) -> str:
        """SSM parameter paths must start with '/'."""
        if not v.startswith("/"):
            msg = f"parameter_path must start with '/': {v!r}"
            raise ValueError(msg)
        return v
