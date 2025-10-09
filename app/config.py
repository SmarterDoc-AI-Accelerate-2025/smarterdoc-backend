from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
from typing import List


class Settings(BaseSettings):
    PORT: int = 8080
    ENVIRONMENT: str = "dev"
    CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["http://localhost:3000"]

    # BigQuery & GCP Settings
    GCP_PROJECT_ID: str | None = None
    GCP_REGION: str = "us-central1"

    BQ_PROJECT: str | None = None
    BQ_CURATED_DATASET: str = "curated"
    COST_TABLE: str | None = None

    BQ_RAW_DATASET: str = "gcs_npi_staging"
    BQ_RAW_TABLE: str = "npi_doctors_row"
    BQ_PROFILES_TABLE: str = "doctor_profiles"

    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"
    EMBEDDING_API_ENDPOINT: str = "us-central1-aiplatform.googleapis.com"
    # TODO: add search api key if using web-search for data enrichment
    GOOGLE_SEARCH_API_KEY: str | None = None
    GOOGLE_SEARCH_CSE_ID: str | None = None
    GCP_MEDIA_BUCKET: str | None=None

    ELASTIC_URL: str = "http://localhost:9200"
    ELASTIC_API_KEY: str | None = None
    ELASTIC_INDEX_DOCTORS: str = "doctors"
    ELASTIC_INDEX_EVIDENCE: str = "evidence"

    WEB_SEARCH_API_KEY: str = ""  # Set in .env for production
    WEB_SEARCH_ENDPOINT: str = "https://custom-search-api.google.com/search"

    INDEXER_BATCH_SIZE: int = 100
    INDEXER_MAX_CONCURRENCY: int = 10

    # ============================================
    # AI Chat & Gen AI Configuration
    # ============================================
    # Generation Configuration
    GENAI_TEMPERATURE: float = 0.7
    GENAI_TOP_P: float = 0.95
    GENAI_TOP_K: int = 40
    GENAI_MAX_OUTPUT_TOKENS: int = 8192
    
    # Safety Settings
    GENAI_SAFETY_THRESHOLD: str = "BLOCK_MEDIUM_AND_ABOVE"
    
    # ============================================
    # Speech-to-Text Configuration
    # ============================================
    # Audio configuration
    SPEECH_SAMPLE_RATE: int = 16000
    SPEECH_LANGUAGE_CODE: str = "en-US"
    SPEECH_ENCODING: str = "LINEAR16"
    SPEECH_MODEL: str = "default"
    
    # Enable automatic punctuation
    SPEECH_ENABLE_AUTOMATIC_PUNCTUATION: bool = True
    
    # Single utterance mode (stop after detecting end of speech)
    SPEECH_SINGLE_UTTERANCE: bool = False

    # TWILIO_ACCOUNT_SID: str | None = None
    # TWILIO_AUTH_TOKEN: str | None = None
    # TWILIO_CALLER_NUMBER: str | None = None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    class Config:
        env_file = ".env"
        extra = 'ignore'


settings = Settings()
