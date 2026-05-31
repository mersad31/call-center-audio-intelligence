from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "STT Service"
    APP_VERSION: str = "1.0.0"

    GAPGPT_API_KEY: str
    GAPGPT_BASE_URL: str = "https://api.gapgpt.app/v1"

    TEMP_DIR: str = "/tmp/stt"

    LOG_DIR: str = "logs"
    LOG_FILE_JSON: str = "logs/app.jsonl"
    
    WHISPER_MODEL: str
    
    GAPGPT_MAX_RETRIES: int
    GAPGPT_RETRY_BASE_DELAY_SEC: float
    GAPGPT_RETRY_MAX_DELAY_SEC: int   
 
  
    ADMIN_SECRET_KEY: str 

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()