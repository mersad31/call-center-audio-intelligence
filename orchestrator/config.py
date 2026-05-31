from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    diarize_url: str = Field(..., alias="DIARIZATION_URL")
    role_url: str = Field(..., alias="ROLE_DETECTION_URL")
    stt_url: str = Field(..., alias="STT_URL")
    silence_from_segments_url: str = Field(..., alias="SILENCE_FROM_SEGMENTS_URL")
    overlap_url: str = Field(..., alias="OVERLAP_URL")
    behavior_url: str = Field(..., alias="BEHAVIOR_URL")
    sentiment_url: str = Field(..., alias="SENTIMENT_URL")
    operator_score_url: str = Field(..., alias="OPERATOR_SCORE_URL")
    admin_secret_key: str = Field(default="super-secret-admin-key", alias="ADMIN_SECRET_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


settings = Settings()
