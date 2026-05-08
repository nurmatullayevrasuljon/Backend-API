from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ─── DATABASE ─────────────────────────────
    DATABASE_URL: str = "sqlite:///./test.db"
    # ─── SECURITY ─────────────────────────────
    SECRET_KEY: str = "super-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── FILE UPLOAD ──────────────────────────
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 5

    # ─── SMS (Eskiz / Playmobile) ─────────────
    SMS_PROVIDER_URL: Optional[str] = None
    SMS_USERNAME: Optional[str] = None
    SMS_PASSWORD: Optional[str] = None
    SMS_FROM: Optional[str] = None

    class Config:
        env_file = ".env"


# global instance
settings = Settings()