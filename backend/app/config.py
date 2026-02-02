"""
Application configuration using pydantic-settings.
All settings are loaded from environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "Bookmark Clustering API"
    debug: bool = False
    
    # Supabase Database
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str  # Direct Postgres connection string
    
    # Rate Limiting
    rate_limit_saves_per_hour: int = 30
    rate_limit_requests_per_minute: int = 100
    
    # Content Fetching
    fetch_timeout_seconds: int = 15
    fetch_max_size_bytes: int = 5_000_000  # 5MB
    fetch_user_agent: str = "GoodPocket/1.0 (Bookmark Service)"
    
    # Batch Job
    batch_job_secret: str = ""  # Secret header for triggering batch jobs
    
    # Embedding Model
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    
    # Clustering
    min_cluster_size: int = 3
    umap_n_components: int = 15
    umap_n_neighbors: int = 10


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
