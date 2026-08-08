from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import settings
from .db import get_session
from .models import APPROVED, PENDING, REJECTED, Template
from .schemas import FileIn, ManifestOut, TemplateOut

router = APIRouter(prefix="/api/moderation/workflows", tags=["moderation"])


def require_admin(authorization: str = Header(default="")):
    if authorization != f"Bearer {settings.admin_token()}":
        raise HTTPException(status_code=401, detail="invalid admin token")


def _pending(session: Session, workflow_id: str) -> Template:
    template = session.scalars(
        select(Template)
        .where(Template.id == workflow_id, Template.status == PENDING)
        .options(selectinload(Template.files))
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="no pending workflow with this id")
    return template


@router.get("", response_model=list[ManifestOut], dependencies=[Depends(require_admin)])
def list_pending(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Template).where(Template.status == PENDING).order_by(Template.submitted_at)
    ).all()
    return [
        ManifestOut(id=t.id, name=t.name, description=t.description, tags=t.tags)
        for t in rows
    ]


@router.get(
    "/{workflow_id}", response_model=TemplateOut, dependencies=[Depends(require_admin)]
)
def get_pending(workflow_id: str, session: Session = Depends(get_session)):
    template = _pending(session, workflow_id)
    return TemplateOut(
        id=template.id,
        name=template.name,
        description=template.description,
        tags=template.tags,
        files=[FileIn(path=f.path, content=f.content) for f in template.files],
    )


@router.post("/{workflow_id}/approve", dependencies=[Depends(require_admin)])
def approve(workflow_id: str, session: Session = Depends(get_session)):
    template = _pending(session, workflow_id)
    # Approving a replacement supersedes the previously approved entry.
    old = session.scalars(
        select(Template).where(Template.id == workflow_id, Template.status == APPROVED)
    ).first()
    if old is not None:
        session.delete(old)
        session.flush()
    template.status = APPROVED
    template.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    return {"id": workflow_id, "status": APPROVED}


@router.post("/{workflow_id}/reject", dependencies=[Depends(require_admin)])
def reject(workflow_id: str, session: Session = Depends(get_session)):
    template = _pending(session, workflow_id)
    template.status = REJECTED
    template.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    return {"id": workflow_id, "status": REJECTED}
