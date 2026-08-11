from pydantic import BaseModel


class WorkflowOut(BaseModel):
    id: str
    downloads: int


class InstallIn(BaseModel):
    install_id: str
    version: str
    os: str
    platform: str
