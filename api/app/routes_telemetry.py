import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .db import get_session
from .models import Install
from .schemas import InstallIn

router = APIRouter(tags=["telemetry"])

# Simple in-memory rate limiter: IP -> last request timestamp
_rate_limit: dict[str, float] = {}
_RATE_LIMIT_SECONDS = 1.0


@router.post("/api/telemetry", status_code=204)
def record_install(
    data: InstallIn,
    request: Request,
    session: Session = Depends(get_session),
):
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    last = _rate_limit.get(client_ip)
    if last is not None and (now - last) < _RATE_LIMIT_SECONDS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Try again later."},
        )
    _rate_limit[client_ip] = now

    session.add(Install(
        install_id=data.install_id,
        version=data.version,
        os=data.os,
        platform=data.platform,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    session.commit()
    return Response(status_code=204)
