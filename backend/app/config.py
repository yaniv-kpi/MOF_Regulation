from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/regdb"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    DEBUG: bool = False
    CRAWL_DELAY_SECONDS: float = 1.5
    MAX_DOCUMENTS: int = 10000

    model_config = {"env_file": ".env"}


settings = Settings()
