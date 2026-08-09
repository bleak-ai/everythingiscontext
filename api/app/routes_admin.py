from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db import get_session
from .models import APPROVED, REJECTED, Template
from .routes_moderation import require_admin
from .schemas import AdminUpdateIn, AdminWorkflowOut

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


def _to_out(t: Template) -> AdminWorkflowOut:
    return AdminWorkflowOut(
        id=t.id,
        name=t.name,
        description=t.description,
        tags=t.tags,
        status=t.status,
        submitted_at=t.submitted_at,
        reviewed_at=t.reviewed_at,
        file_count=len(t.files),
    )


@router.get("/workflows", response_model=list[AdminWorkflowOut])
def list_all(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Template).options(selectinload(Template.files)).order_by(Template.id)
    ).all()
    return [_to_out(t) for t in rows]


@router.patch("/workflows/{workflow_id}", response_model=AdminWorkflowOut)
def update_metadata(
    workflow_id: str, body: AdminUpdateIn, session: Session = Depends(get_session)
):
    template = session.scalars(
        select(Template)
        .where(Template.id == workflow_id)
        .options(selectinload(Template.files))
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    if body.name is not None:
        template.name = body.name
    if body.description is not None:
        template.description = body.description
    if body.tags is not None:
        template.tags = body.tags
    session.commit()
    session.refresh(template)
    return _to_out(template)


@router.post("/workflows/{workflow_id}/publish")
def publish_workflow(workflow_id: str, session: Session = Depends(get_session)):
    template = session.scalars(
        select(Template).where(Template.id == workflow_id, Template.status == REJECTED)
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="no rejected workflow with this id")
    template.status = APPROVED
    template.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    return {"id": workflow_id, "status": APPROVED}


@router.delete("/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, session: Session = Depends(get_session)):
    template = session.scalars(
        select(Template).where(Template.id == workflow_id)
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    session.delete(template)
    session.commit()
    return {"deleted": workflow_id}
