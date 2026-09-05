from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_VERSION: str = "v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "chrome-extension://dbfcpaoidbcbijoafhjkhamkcbiegabn"]

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str

    # ─── Redis ────────────────────────────────────────────────
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # ─── MinIO ────────────────────────────────────────────────
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_SCREENSHOTS: str = "apds-screenshots"
    MINIO_BUCKET_EMAIL_BODIES: str = "apds-email-bodies"
    MINIO_BUCKET_MODELS: str = "apds-models"

    # ─── JWT ──────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # ─── Internal Services ────────────────────────────────────
    NLP_SERVICE_URL: str
    URL_SERVICE_URL: str
    VISUAL_SERVICE_URL: str
    ADVERSARIAL_SERVICE_URL: str
    FUSION_SERVICE_URL: str
    INTEL_SERVICE_URL: str
    # doc 6.4: refresh threat feeds every 15 min. Kept as a config value
    # (not hardcoded in celery_app.py) so it matches intel-service's own
    # FEED_REFRESH_INTERVAL_MINUTES without editing two files if it changes.
    INTEL_FEED_REFRESH_SECONDS: int = 900
    FEEDBACK_SERVICE_URL: str
    TRAINING_SERVICE_URL: str
    DASHBOARD_API_URL: str

    # ─── ML ───────────────────────────────────────────────────
    MODEL_STORE_PATH: str = "/models"
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    SCREENSHOT_TIMEOUT_MS: int = 2000

    # ─── Threat Intel ─────────────────────────────────────────
    PHISHTANK_API_KEY: str = ""
    OPENPHISH_FEED_URL: str = "https://openphish.com/feed.txt"
    URLHAUS_API_URL: str = "https://urlhaus-api.abuse.ch/v1"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()