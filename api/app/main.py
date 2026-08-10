from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes_admin import router as admin_router
from .routes_public import router as public_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="gcontext workflows API", lifespan=lifespan)
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


@app.get("/health")
def health():
    return {"status": "ok"}
