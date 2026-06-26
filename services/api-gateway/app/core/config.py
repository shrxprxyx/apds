from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ─── App ─────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_VERSION: str = "v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # ─── Database ─────────────────────────────────────────────
    DATABASE_URL: str

    # ─── Redis ────────────────────────────────────────────────
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

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
    FEEDBACK_SERVICE_URL: str
    TRAINING_SERVICE_URL: str
    DASHBOARD_API_URL: str

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()