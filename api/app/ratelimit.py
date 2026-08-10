"""Shared rate limiter. Lives in its own module so routes and main can both
import it without a circular import."""

from fastapi import Request
from slowapi import Limiter


def client_ip(request: Request) -> str:
    # The API runs behind exactly one trusted reverse proxy (Coolify's
    # Traefik), which appends the real client IP as the last entry of
    # X-Forwarded-For. Earlier entries are client-supplied and spoofable,
    # so key on the last one. Fall back to the direct peer for local runs.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.rsplit(",", 1)[-1].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip)
