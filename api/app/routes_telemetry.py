from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .db import get_session
from .models import Install
from .schemas import InstallIn

router = APIRouter(tags=["telemetry"])


@router.post("/api/telemetry", status_code=204)
def record_install(data: InstallIn, session: Session = Depends(get_session)):
    session.add(Install(
        install_id=data.install_id,
        version=data.version,
        os=data.os,
        platform=data.platform,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    session.commit()
    return Response(status_code=204)
