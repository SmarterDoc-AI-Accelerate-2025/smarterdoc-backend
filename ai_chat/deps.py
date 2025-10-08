"""
Dependency injection for AI chat service.
"""
from typing import Generator
from .services.chat_service import GenAIChatService, get_chat_service as _get_chat_service
from .services.speech_service import SpeechToTextService, get_speech_service as _get_speech_service


def get_chat_service() -> GenAIChatService:
    """
    Dependency injection for chat service.
    
    Returns:
        GenAIChatService instance
    """
    return _get_chat_service()


def get_speech_service() -> SpeechToTextService:
    """
    Dependency injection for speech-to-text service.
    
    Returns:
        SpeechToTextService instance
    """
    return _get_speech_service()

