from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dynamically find the root directory of the repository (apds/)
# config.py -> core -> app -> fusion-service -> apds
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ─── Redis (doc 7.2: APDS:MODEL:WEIGHTS, TTL 25h) ─────────
    REDIS_URL: str
    WEIGHTS_CACHE_KEY: str = "APDS:MODEL:WEIGHTS"

    # ─── Default Fusion Weights (doc 4.5.1) ───────────────────
    # Used until training-service starts publishing calibrated
    # weights nightly. w1..w4 correspond to nlp, url, visual,
    # adversarial. Must sum to a sane range for log-odds combine.
    DEFAULT_WEIGHT_NLP: float = 0.30
    DEFAULT_WEIGHT_URL: float = 0.30
    DEFAULT_WEIGHT_VISUAL: float = 0.25
    DEFAULT_WEIGHT_ADVERSARIAL: float = 0.15
    DEFAULT_BIAS: float = 0.0

    # ─── Decision Thresholds (doc 4.5.1) ──────────────────────
    THRESHOLD_BLOCK: float = 0.85
    THRESHOLD_WARN: float = 0.55

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()