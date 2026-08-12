"""Schema definitions for gcontext manifests."""

from pydantic import BaseModel


class ModuleManifest(BaseModel):
    name: str
    description: str
    author: str = ""
    tags: list[str] = []


class ConnectionManifest(BaseModel):
    name: str
    description: str = ""
    # Capability kind; values come from kinds.CONNECTION_KINDS. Optional,
    # not validated at load time (the validator is a separate concern).
    kind: str = ""
    secrets: list[str] = []
    deps: list[str] = []
