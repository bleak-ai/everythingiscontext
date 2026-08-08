from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import init_db
from .routes_moderation import router as moderation_router
from .routes_public import router as public_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="gcontext workflows API", lifespan=lifespan)
app.include_router(public_router)
app.include_router(moderation_router)


@app.get("/health")
def health():
    return {"status": "ok"}
