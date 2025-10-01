from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, field_validator
from typing import List


class Settings(BaseSettings):
    PORT: int = 8080
    ENVIRONMENT: str = "dev"
    CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["http://localhost:3000"]

    ELASTIC_URL: str = "http://localhost:9200"
    ELASTIC_API_KEY: str | None = None
    ELASTIC_INDEX_DOCTORS: str = "doctors"
    ELASTIC_INDEX_EVIDENCE: str = "evidence"

    BQ_PROJECT: str | None = None
    BQ_DATASET: str | None = None
    COST_TABLE: str | None = None

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


settings = Settings()
