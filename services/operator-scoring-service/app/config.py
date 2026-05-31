from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()

class Settings(BaseModel):
    gapgpt_base_url: str = os.getenv("GAPGPT_BASE_URL")
    gapgpt_api_key: str = os.getenv("GAPGPT_API_KEY")
    model_name: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    temperature: float = float(os.getenv("TEMPERATURE", "0.2"))
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "90"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    admin_secret_key: str = os.getenv("ADMIN_SECRET_KEY", "super_secret_admin_key")


    @property
    def validated(self):
        if not self.gapgpt_api_key:
            raise ValueError("GAPGPT_API_KEY is not set")

        if not self.gapgpt_base_url:
            raise ValueError("GAPGPT_BASE_URL is not set")

        return self

settings = Settings().validated

