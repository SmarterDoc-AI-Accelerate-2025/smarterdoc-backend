from app.config import settings
from app.services.chat_service import GenAIChatService, get_chat_service as _get_chat_service
from app.services.speech_service import SpeechToTextService, get_speech_service as _get_speech_service
from typing import Any, Generator
from google.cloud import bigquery
from google.auth import default

import logging

_logger = logging.getLogger(__name__)
_bq_client: bigquery.Client | None = None


# fastAPI dependency to yield a shared BQ client per process
# safe to reuse across requests and threads, each worker has own instance.
def get_bq() -> Generator[bigquery.Client, None, None]:
    global _bq_client
    if _bq_client is None:
        creds, project = default()
        _bq_client = bigquery.Client(project=project
                                     or settings.GCP_PROJECT_ID,
                                     credentials=creds)
        _logger.info("Initialized global BigQuery client.")
    yield _bq_client


# for non-FastAPI code paths (scripts/jobs)
def get_bq_sync() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        creds, project = default()
        _bq_client = bigquery.Client(project=project
                                     or settings.GCP_PROJECT_ID,
                                     credentials=creds)
    return _bq_client


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
