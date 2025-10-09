######################
# Dependencies to reuse
######################

# from elasticsearch import Elasticsearch
# from .config import settings

# _es_client: Elasticsearch | None = None

# def get_elastic() -> Elasticsearch:
#     global _es_client
#     if _es_client is None:
#         api_key = settings.ELASTIC_API_KEY
#         kwargs = {"hosts": [settings.ELASTIC_URL]}
#         if api_key:
#             kwargs["api_key"] = api_key
#         _es_client = Elasticsearch(**kwargs)
#     return _es_client

from elasticsearch import Elasticsearch
from app.config import settings
from app.services.chat_service import GenAIChatService, get_chat_service as _get_chat_service
from app.services.speech_service import SpeechToTextService, get_speech_service as _get_speech_service
from typing import Any, Generator
import logging

logger = logging.getLogger(__name__)

# Global variable to hold the client instance (if needed for singleton pattern)
_es_client = None


def get_elastic() -> Generator[Any, None, None]:
    """
    Dependency resolver that attempts to yield a live Elasticsearch client.
    
    If the connection fails (e.g., Elastic is not yet ready), it yields None 
    and logs the error, allowing the FastAPI service to start (using mock search).
    """
    global _es_client

    # 1. MOCK/LIVE CHECK: If client is already initialized, use it
    if _es_client is not None:
        yield _es_client
        return

    # 2. ATTEMPT LIVE CONNECTION
    try:
        api_key = settings.ELASTIC_API_KEY
        # NOTE: Your docker-compose maps port 9200 to elastic-local:9200
        # For deployment, this will be the Cloud Elastic URL.
        kwargs = {"hosts": [settings.ELASTIC_URL]}

        if api_key:
            kwargs["api_key"] = api_key

        client = Elasticsearch(**kwargs)
        client.info()  # Test the connection

        logger.info("Successfully connected to live Elasticsearch.")
        _es_client = client
        yield client

    except Exception as e:
        logger.warning(
            f"Failed to connect to Elasticsearch. Search endpoints will be MOCKED. Error: {e}"
        )

        # 3. YIELD MOCK: Yield None (or a dummy object) to allow the app to start
        # The search endpoint's mock function (hybrid_search) is designed to handle this None client.
        yield None

    finally:
        # FastAPI cleanup logic is typically handled implicitly or by using yield.
        pass


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
