#app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    SERVICE_NAME: str = "operator-behavior-detection"

    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2

    LLM_RETRY_COUNT: int = 2
    LLM_RETRY_BACKOFF: float = 1.5

    LLM_BREAKER_THRESHOLD: int = 3
    LLM_BREAKER_COOLDOWN: int = 30


    LLM_PRIMARY_MODEL: str = "gemini-2.5-pro"
    LLM_FALLBACK_MODEL: str = "gemini-2.5-flash"

    LOG_JSON_FILE: str = "logs/app.log"

    GAPGPT_API_KEY: str
    GAPGPT_BASE_URL: str
    
    ADMIN_SECRET_KEY: str
 
    class Config:
        env_file = ".env"


settings = Settings()