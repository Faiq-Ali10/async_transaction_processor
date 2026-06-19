from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Financial Transaction Processor"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/transactions"
    redis_url: str = "redis://redis:6379/0"
    upload_dir: str = "/app/storage/uploads"
    result_dir: str = "/app/storage/results"
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    llm_batch_size: int = 10
    llm_timeout_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
