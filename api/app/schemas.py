from pydantic import BaseModel


class WorkflowOut(BaseModel):
    id: str
    downloads: int
