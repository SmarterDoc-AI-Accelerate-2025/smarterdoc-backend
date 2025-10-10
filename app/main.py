import os
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

# Configure CORS FIRST - before any routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add startup logging
@app.on_event("startup")
async def startup_event():
    port = int(os.environ.get("PORT", 8080))
    log.info(f"Starting SmarterDoc Backend on port {port}")
    log.info(f"Environment: {settings.ENVIRONMENT}")
    log.info("Application startup complete")
    log.info("CORS configured for frontend domains")

# Include API routers
app.include_router(api_router, prefix="/api")
log.info("API routes included")

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    log.info(f"✅ Mounted static files from {static_dir}")

# Root endpoints
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "SmarterDoc Backend API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
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

# Add a test endpoint for CORS
@app.options("/{rest_of_path:path}")
async def preflight_handler(rest_of_path: str):
    """Handle preflight OPTIONS requests for CORS"""
    return {}

@app.get("/cors-test")
async def cors_test():
    """Test endpoint to verify CORS is working"""
    return {
        "message": "CORS test successful",
        "cors_enabled": True,
        "frontend_url": "https://smarterdoc-frontend-1094971678787.us-central1.run.app"
    }