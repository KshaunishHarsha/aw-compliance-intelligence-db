from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # Database
    database_url: str
    sync_database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""

    # Storage
    storage_provider: str = "supabase"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_bucket_name: str = ""
    aws_region: str = "us-east-1"
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_bucket: str = "documents"

    # App
    environment: str = "development"
    secret_key: str = "changeme"
    log_level: str = "INFO"

    # Auth
    access_token_expire_minutes: int = 1440  # 24 hours
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
