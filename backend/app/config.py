from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
