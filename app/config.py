from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://platform:platform@localhost:5432/platform"
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    kubeconfig_path: str = str(Path.home() / ".kube" / "config")
    kubernetes_context: str | None = "k3d-student-platform"
    ingress_port: int = 8081
    max_active_environments_per_user: int = 2
    default_ttl_hours: int = 8
    job_poll_seconds: int = 2
    job_max_attempts: int = 3
    job_stale_seconds: int = 120
    cleanup_failed_environments: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
