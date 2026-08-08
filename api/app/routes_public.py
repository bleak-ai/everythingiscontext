from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db import get_session
from .manifest import BundleError, parse_manifest, validate_files
from .models import APPROVED, PENDING, Template, TemplateFile
from .schemas import FileIn, ManifestOut, SubmitIn, SubmitOut, TemplateOut

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=list[ManifestOut])
def list_workflows(session: Session = Depends(get_session)):
    rows = session.scalars(
        select(Template).where(Template.status == APPROVED).order_by(Template.id)
    ).all()
    return [
        ManifestOut(id=t.id, name=t.name, description=t.description, tags=t.tags)
        for t in rows
    ]


@router.get("/{workflow_id}", response_model=TemplateOut)
def get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    template = session.scalars(
        select(Template)
        .where(Template.id == workflow_id, Template.status == APPROVED)
        .options(selectinload(Template.files))
    ).first()
    if template is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return TemplateOut(
        id=template.id,
        name=template.name,
        description=template.description,
        tags=template.tags,
        files=[FileIn(path=f.path, content=f.content) for f in template.files],
    )


@router.post("", response_model=SubmitOut, status_code=201)
def submit_workflow(body: SubmitIn, session: Session = Depends(get_session)):
    files = [f.model_dump() for f in body.files]
    try:
        validate_files(files)
        manifest = parse_manifest(files)
    except BundleError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # A new submission replaces an existing pending entry for the same id.
    # An approved entry stays live until the replacement is approved.
    existing_pending = session.scalars(
        select(Template).where(Template.id == manifest["id"], Template.status == PENDING)
    ).first()
    if existing_pending is not None:
        session.delete(existing_pending)
        session.flush()

    template = Template(
        id=manifest["id"],
        name=manifest["name"],
        description=manifest["description"],
        tags=manifest["tags"],
        status=PENDING,
        files=[TemplateFile(path=f["path"], content=f["content"]) for f in files],
    )
    session.add(template)
    session.commit()
    return SubmitOut(status=PENDING, **manifest)
