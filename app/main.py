from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.v1 import api_router
from .config import settings
from .util.logging import setup_logging

log = setup_logging()

# Create FastAPI app
app = FastAPI(
    title="SmarterDoc Backend", 
    version="0.1.0",
    description="SmarterDoc Backend API with AI Chat and Speech-to-Text capabilities"
)

# Configure CORS - Following ai_chat working pattern
log.info(f"🌐 CORS: Allowing all origins ({'development' if settings.ENVIRONMENT == 'dev' else 'production'} mode)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for WebSocket compatibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers FIRST (like ai_chat)
app.include_router(api_router, prefix="/api")

# Mount static files AFTER routes (like ai_chat)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    log.info(f"✓ Mounted static files from {static_dir}")

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "SmarterDoc Backend API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "speech_demo": "/static/speech_demo.html",
        "environment": settings.ENVIRONMENT
    }

@app.get("/healthz")
def health():
    """Health check endpoint."""
    return {"ok": True, "env": settings.ENVIRONMENT}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "SmarterDoc Backend",
        "environment": settings.ENVIRONMENT
    }

@app.get("/hello")
def hello_world():
    """Hello world endpoint."""
    return {"message": "Hello Hogan"}
