from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.v1 import api_router
from .config import settings
from .util.logging import setup_logging

log = setup_logging()

app = FastAPI(title="SmarterDoc Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def health():
    return {"ok": True, "env": settings.ENVIRONMENT}


app.include_router(api_router)
