from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    scheduler_enabled: bool = True

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ky"

    llm_base_url: str = "https://your-mirror.example.com/v1"
    llm_api_key: str = "replace-me"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.2

    embedding_base_url: str = "https://your-mirror.example.com/v1"
    embedding_api_key: str = "replace-me"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 465
    smtp_user: str = "your-email@example.com"
    smtp_password: str = "replace-me"
    smtp_use_tls: bool = True
    smtp_starttls: bool = False
    email_from: str = "your-email@example.com"
    email_to: str = "your-email@example.com"
    email_enabled: bool = False

    daily_report_time: str = "08:00"
    timezone: str = "Asia/Shanghai"
    storage_dir: Path = Field(default=Path("./storage"))
    topics_config_path: Path = Field(default=Path("./configs/topics.yaml"))
    runtime_config_path: Path = Field(default=Path("./storage/runtime_config.json"))
    mcp_local_server_enabled: bool = True

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def reports_dir(self) -> Path:
        return self.storage_dir / "reports"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    return settings
