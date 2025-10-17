from app.config import settings
from app.services.chat_service import GenAIChatService, get_chat_service as _get_chat_service
from app.services.speech_service import SpeechToTextService, get_speech_service as _get_speech_service
from typing import Any, Generator
from google.cloud import bigquery
from google.auth import default
from app.services.gemini_client import GeminiClient
from app.services.vertex_vector_search_service import VertexVectorSearchService
from app.services.bq_doctor_service import BQDoctorService
import logging

_logger = logging.getLogger(__name__)

# Global Singleton Instances
_bq_client: bigquery.Client | None = None
_gemini_client: GeminiClient | None = None
_bq_service: BQDoctorService | None = None
_vector_search_service: VertexVectorSearchService | None = None

# fastAPI dependency to yield a shared client per process
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


def get_gemini_client() -> GeminiClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()  # Client init is the expensive part
        _logger.info("Initialized global GeminiClient (Singleton).")
    return _gemini_client


def get_bq_doctor_service() -> BQDoctorService:
    global _bq_service
    if _bq_service is None:
        # Reuses the synchronous BQ client instance
        _bq_service = BQDoctorService(client=get_bq_sync())
        _logger.info("Initialized global BQDoctorService (Singleton).")
    return _bq_service


def get_vector_search_service() -> VertexVectorSearchService:
    global _vector_search_service
    if _vector_search_service is None:
        # Requires BQ service to be initialized first for the lookup dependency
        _vector_search_service = VertexVectorSearchService(
            bq_service=get_bq_doctor_service())
        _logger.info(
            "Initialized global VertexVectorSearchService (Singleton).")
    return _vector_search_service


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
