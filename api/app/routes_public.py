import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .db import get_session
from .models import Workflow
from .schemas import WorkflowOut

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(
    workflow_id: str, request: Request, session: Session = Depends(get_session)
):
    if not SLUG_RE.match(workflow_id):
        raise HTTPException(status_code=404, detail="invalid workflow id")

    if request.headers.get("x-source") == "site":
        row = session.scalars(
            select(Workflow).where(Workflow.id == workflow_id)
        ).first()
        return WorkflowOut(id=workflow_id, downloads=row.downloads if row else 0)

    stmt = (
        insert(Workflow)
        .values(id=workflow_id, downloads=1)
        .on_conflict_do_update(
            index_elements=[Workflow.id],
            set_={"downloads": Workflow.downloads + 1},
        )
        .returning(Workflow.downloads)
    )
    result = session.execute(stmt)
    session.commit()
    count = result.scalar_one()
    return WorkflowOut(id=workflow_id, downloads=count)
