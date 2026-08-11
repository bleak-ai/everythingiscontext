import re

from pydantic import BaseModel, field_validator


class WorkflowOut(BaseModel):
    id: str
    downloads: int


_SEMVER_RE = re.compile(r"^[0-9]+(\.[0-9]+){0,4}$")
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class InstallIn(BaseModel):
    install_id: str
    version: str
    os: str
    platform: str

    @field_validator("install_id")
    @classmethod
    def validate_install_id(cls, v: str) -> str:
        if not _UUID4_RE.match(v):
            raise ValueError("install_id must be a valid UUID v4")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if len(v) > 20 or not _SEMVER_RE.match(v):
            raise ValueError("version must be digits and dots, max 20 chars")
        return v

    @field_validator("os", "platform")
    @classmethod
    def validate_short_string(cls, v: str) -> str:
        if len(v) > 50:
            raise ValueError("field must be 50 characters or fewer")
        if "\n" in v or "\r" in v:
            raise ValueError("field must not contain newlines")
        return v
