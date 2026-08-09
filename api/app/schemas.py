from datetime import datetime

from pydantic import BaseModel, model_validator


class FileIn(BaseModel):
    path: str
    content: str


class SubmitIn(BaseModel):
    files: list[FileIn]


class ManifestOut(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]


class SubmitOut(ManifestOut):
    status: str


class TemplateOut(ManifestOut):
    files: list[FileIn]


class AdminWorkflowOut(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]
    status: str
    submitted_at: datetime
    reviewed_at: datetime | None
    file_count: int


class AdminUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.name is None and self.description is None and self.tags is None:
            raise ValueError("at least one field must be provided")
        return self
