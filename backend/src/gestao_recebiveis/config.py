from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://gestao_recebiveis@db:5432/gestao_recebiveis"
    demo_mode: bool = False
    session_secret: str = ""
    frontend_origin: str = "http://localhost:3101"
    cookie_secure: bool = False
    session_hours: int = Field(default=8, ge=1, le=24)
    lease_seconds: int = Field(default=60, ge=3)
    heartbeat_seconds: int = Field(default=20, gt=0)
    max_attempts: int = Field(default=5, ge=1, le=20)
    worker_poll_seconds: float = Field(default=1.0, gt=0, le=60)
    demo_retry_base_seconds: float = Field(default=1.0, gt=0, le=30)

    def validate_runtime(self) -> None:
        if self.heartbeat_seconds >= self.lease_seconds:
            raise ValueError("HEARTBEAT_SECONDS deve ser menor que LEASE_SECONDS.")
        if len(self.session_secret) < 32:
            raise ValueError("SESSION_SECRET deve ter pelo menos 32 caracteres.")
        if not self.demo_mode and not self.cookie_secure:
            raise ValueError("Fora do demo, COOKIE_SECURE deve estar habilitado.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
