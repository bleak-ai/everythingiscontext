from pydantic import BaseModel


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
