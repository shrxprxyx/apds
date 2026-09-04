from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"
class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str

    # ─── Redis (doc 6.4: APDS:TI:DOMAIN:{domain} cache) ───────
    REDIS_URL: str
    TI_CACHE_PREFIX: str = "APDS:TI:DOMAIN:"
    TI_CACHE_TTL_SECONDS: int = 900  # 15 min, matches feed refresh interval

    # ─── Threat Feeds ───────────────────────────────────────────
    # Same variable names as api-gateway's config.py — both services
    # read from the one shared .env, so nothing new to add there.
    PHISHTANK_API_KEY: str = ""
    OPENPHISH_FEED_URL: str = "https://openphish.com/feed.txt"
    URLHAUS_API_URL: str = "https://urlhaus-api.abuse.ch/v1"
    URLHAUS_API_KEY: str = ""

    # ─── Polling ─────────────────────────────────────────────────
    FEED_REFRESH_INTERVAL_MINUTES: int = 15
    FEED_FETCH_TIMEOUT_SECONDS: int = 30

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()