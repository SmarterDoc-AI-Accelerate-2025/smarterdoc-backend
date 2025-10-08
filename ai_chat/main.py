"""
Main FastAPI application for AI Chat service.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import router as v1_router
from .config import ChatConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Chat Service",
    description="Google Gen AI powered chat service with streaming support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(v1_router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting AI Chat Service...")
    try:
        ChatConfig.validate(strict=False)
        config_summary = ChatConfig.get_config_summary()
        logger.info(f"Configuration: {config_summary}")
        logger.info("Configuration validated successfully")
    except Exception as e:
        logger.error(f"Configuration validation failed: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down AI Chat Service...")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AI Chat Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "AI Chat Service",
    }


if __name__ == "__main__":
    import uvicorn
    import sys
    from pathlib import Path
    
    # Ensure parent directory is in path for imports
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    # Run the application
    uvicorn.run(
        "ai_chat.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

