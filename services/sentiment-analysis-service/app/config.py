# config.py
import os

from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    model_path: Path = Path("./models/parsbert-sentiment/")
    max_length: int = 128
    device: str = "cpu"
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY")


settings = Settings()
