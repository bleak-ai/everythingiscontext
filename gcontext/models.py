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
    secrets: list[str] = []
    deps: list[str] = []
