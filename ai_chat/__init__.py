"""
AI Chat module for Google Gen AI integration.

This module provides a complete FastAPI-based chat service powered by Google Gen AI.

Project Structure:
- api/v1/: API endpoints (chat, streaming, health checks)
- models/: Pydantic schemas and data models
- services/: Business logic and AI service integration
- config.py: Configuration management
- deps.py: Dependency injection
- main.py: FastAPI application entry point

Quick Start:
    1. Set environment variables:
       export GOOGLE_CLOUD_PROJECT="your-project-id"
       export GOOGLE_CLOUD_LOCATION="us-central1"
    
    2. Install dependencies:
       pip install -r requirements.txt
    
    3. Run the service:
       python -m ai_chat.main
       # or
       uvicorn ai_chat.main:app --reload
    
    4. Access API docs:
       http://localhost:8000/docs
"""
from .main import app
from .services import GenAIChatService, get_chat_service
from .models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    HealthCheckResponse,
)

__all__ = [
    "app",
    "GenAIChatService",
    "get_chat_service",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatStreamRequest",
    "HealthCheckResponse",
]

__version__ = "1.0.0"

