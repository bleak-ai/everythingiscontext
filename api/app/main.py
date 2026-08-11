import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes_admin import router as admin_router
from .routes_public import router as public_router
from .routes_telemetry import router as telemetry_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


_docs_enabled = os.environ.get("API_DOCS") == "1"

app = FastAPI(
    title="gcontext workflows API",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gcontext.ai",
        "https://www.gcontext.ai",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public_router)
app.include_router(admin_router)
app.include_router(telemetry_router)


@app.get("/health")
def health():
    return {"status": "ok"}
