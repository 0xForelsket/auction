from pathlib import Path
from typing import List

from sqlalchemy.engine.url import make_url

from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DEBUG: bool = True
    PROJECT_NAME: str = "Auction OCR API"

    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    DATABASE_URL: str = "postgresql+asyncpg://auction:auction@db:5432/auction"
    DATABASE_URL_SYNC: str | None = None
    REDIS_URL: str = "redis://redis:6379/0"

    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "auction-ocr"

    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    PASSWORD_HASH_SCHEME: str = "bcrypt"

    UPLOAD_MAX_SIZE_MB: int = 15
    PIPELINE_VERSION: str = "v1"

    def resolved_sync_db_url(self) -> str:
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        url = make_url(self.DATABASE_URL)
        if url.drivername.endswith("+asyncpg"):
            url = url.set(drivername=url.drivername.replace("+asyncpg", ""))
        return url.render_as_string(hide_password=False)


settings = Settings()
