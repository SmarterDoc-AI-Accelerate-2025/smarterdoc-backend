"""
Configuration for Google Gen AI chat service using Vertex AI.

Reference: https://cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Try loading from current directory
    load_dotenv()


class ChatConfig:
    """Configuration for Google Gen AI chat service with Vertex AI."""
    
    # ============================================
    # Vertex AI Configuration
    # ============================================
    # Use Vertex AI (default: True)
    # Set GOOGLE_GENAI_USE_VERTEXAI=True to enable Vertex AI mode
    USE_VERTEXAI: bool = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'True').lower() == 'true'
    
    # Google Cloud Project ID (required for Vertex AI)
    # Example: export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT
    PROJECT_ID: str = os.getenv('GOOGLE_CLOUD_PROJECT', '')
    
    # Google Cloud Location/Region (default: us-central1)
    # Example: export GOOGLE_CLOUD_LOCATION=us-central1
    LOCATION: str = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
    
    # ============================================
    # Model Configuration
    # ============================================
    # Default model to use
    DEFAULT_MODEL: str = os.getenv('GENAI_MODEL', 'gemini-2.5-flash')
    
    # Generation Configuration
    DEFAULT_TEMPERATURE: float = float(os.getenv('GENAI_TEMPERATURE', '0.7'))
    DEFAULT_TOP_P: float = float(os.getenv('GENAI_TOP_P', '0.95'))
    DEFAULT_TOP_K: int = int(os.getenv('GENAI_TOP_K', '40'))
    DEFAULT_MAX_OUTPUT_TOKENS: int = int(os.getenv('GENAI_MAX_OUTPUT_TOKENS', '8192'))
    
    # Safety Settings
    SAFETY_BLOCK_THRESHOLD: str = os.getenv('GENAI_SAFETY_THRESHOLD', 'BLOCK_MEDIUM_AND_ABOVE')
    
    # ============================================
    # Speech-to-Text Configuration
    # ============================================
    # Audio configuration
    SPEECH_SAMPLE_RATE: int = int(os.getenv('SPEECH_SAMPLE_RATE', '16000'))
    SPEECH_LANGUAGE_CODE: str = os.getenv('SPEECH_LANGUAGE_CODE', 'en-US')
    SPEECH_ENCODING: str = os.getenv('SPEECH_ENCODING', 'LINEAR16')
    SPEECH_MODEL: str = os.getenv('SPEECH_MODEL', 'default')
    
    # Enable automatic punctuation
    SPEECH_ENABLE_AUTOMATIC_PUNCTUATION: bool = os.getenv('SPEECH_ENABLE_AUTOMATIC_PUNCTUATION', 'True').lower() == 'true'
    
    # Single utterance mode (stop after detecting end of speech)
    SPEECH_SINGLE_UTTERANCE: bool = os.getenv('SPEECH_SINGLE_UTTERANCE', 'False').lower() == 'true'
    
    @classmethod
    def validate(cls, strict: bool = True) -> bool:
        """
        Validate configuration.
        
        Args:
            strict: If True, raise error on missing config. If False, only warn.
            
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If required configuration is missing and strict=True
        """
        errors = []
        
        if not cls.USE_VERTEXAI:
            errors.append(
                "GOOGLE_GENAI_USE_VERTEXAI should be set to 'True' for Vertex AI mode"
            )
        
        if not cls.PROJECT_ID:
            errors.append(
                "GOOGLE_CLOUD_PROJECT environment variable is required. "
                "Example: export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT"
            )
        
        if not cls.LOCATION:
            errors.append(
                "GOOGLE_CLOUD_LOCATION environment variable is required. "
                "Example: export GOOGLE_CLOUD_LOCATION=us-central1"
            )
        
        if errors:
            error_msg = "\n".join([f"  - {err}" for err in errors])
            full_msg = (
                "Configuration validation failed:\n"
                f"{error_msg}\n\n"
                "Please set the required environment variables:\n"
                "  export GOOGLE_CLOUD_PROJECT=your-project-id\n"
                "  export GOOGLE_CLOUD_LOCATION=us-central1\n"
                "  export GOOGLE_GENAI_USE_VERTEXAI=True\n\n"
                "See: https://cloud.google.com/vertex-ai/generative-ai/docs/start/quickstart"
            )
            
            if strict:
                raise ValueError(full_msg)
            else:
                import warnings
                warnings.warn(full_msg)
                return False
        
        return True
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """Get a summary of current configuration."""
        return {
            'use_vertexai': cls.USE_VERTEXAI,
            'project_id': cls.PROJECT_ID or '(not set)',
            'location': cls.LOCATION,
            'model': cls.DEFAULT_MODEL,
            'temperature': cls.DEFAULT_TEMPERATURE,
            'max_tokens': cls.DEFAULT_MAX_OUTPUT_TOKENS,
        }

