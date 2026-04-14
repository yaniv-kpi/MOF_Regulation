from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Default to SQLite so the app works without any external database.
    # Override with a real PostgreSQL URL (e.g. via Neon/Supabase) to get
    # full FTS performance.
    DATABASE_URL: str = "sqlite:///./regdb.sqlite"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]
    DEBUG: bool = False
    CRAWL_DELAY_SECONDS: float = 1.0
    MAX_DOCUMENTS: int = 10000

    model_config = {"env_file": ".env"}


settings = Settings()
