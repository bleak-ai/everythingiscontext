from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import settings
from .db import get_session
from .models import Install, Workflow
from .schemas import WorkflowOut


def require_admin(authorization: str = Header(default="")):
    if authorization != f"Bearer {settings.admin_token()}":
        raise HTTPException(status_code=401, detail="invalid admin token")


router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.get("/workflows", response_model=list[WorkflowOut])
def list_all(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Workflow).order_by(Workflow.downloads.desc())
    ).all()
    return [WorkflowOut(id=w.id, downloads=w.downloads) for w in rows]


@router.get("/installs")
def list_installs(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Install).order_by(Install.id.desc()).limit(200)
    ).all()
    return [
        {
            "install_id": r.install_id,
            "version": r.version,
            "os": r.os,
            "platform": r.platform,
            "created_at": r.created_at,
        }
        for r in rows
    ]
