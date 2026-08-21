from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_default_data_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / "data",
        Path.home() / "Desktop" / "\u5be6\u7fd2\u500b\u6848" / "abs2025" / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Baseball Analysis API"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )
    data_dir: Path = Field(default_factory=resolve_default_data_dir)
    legacy_project_dir: Path | None = None


settings = Settings()
