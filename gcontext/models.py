"""Schema definitions for gcontext manifests."""

from pydantic import BaseModel


class ModuleManifest(BaseModel):
    name: str
    description: str
    author: str = ""
    tags: list[str] = []
