from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# config.py → core → app → intel-service
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str

    # ─── Redis ────────────────────────────────────────────────
    REDIS_URL: str
    TI_CACHE_PREFIX: str = "APDS:TI:DOMAIN:"
    TI_CACHE_TTL_SECONDS: int = 900

    # ─── Threat Feeds ─────────────────────────────────────────
    PHISHTANK_API_KEY: str = ""
    OPENPHISH_FEED_URL: str = "https://openphish.com/feed.txt"
    URLHAUS_API_URL: str = "https://urlhaus-api.abuse.ch/v1"
    URLHAUS_API_KEY: str = ""

    # ─── Polling ──────────────────────────────────────────────
    FEED_REFRESH_INTERVAL_MINUTES: int = 15
    FEED_FETCH_TIMEOUT_SECONDS: int = 30

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()