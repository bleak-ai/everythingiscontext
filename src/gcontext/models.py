"""Schema definitions for gcontext manifests."""

from pydantic import BaseModel


class ModuleManifest(BaseModel):
    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    tags: list[str] = []


class ConnectionManifest(BaseModel):
    name: str
    description: str = ""
    secrets: list[str] = []
    deps: list[str] = []


class FlowStep(BaseModel):
    id: str
    description: str = ""
    needs: list[str] = []
    produces: list[str] = []
    instructions: str = ""


class FlowManifest(BaseModel):
    name: str
    description: str = ""
    steps: list[FlowStep] = []
