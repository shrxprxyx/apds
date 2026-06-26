from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ─── Model (doc 4.1.1) ────────────────────────────────────
    # Base: distilbert-base-uncased
    # Fine-tuned classification head on [CLS] token
    # Input truncated to 512 tokens
    NLP_MODEL_NAME: str = "distilbert-base-uncased"
    NLP_MODEL_PATH: str = "/models/nlp/phishing_distilbert"
    MODEL_STORE_PATH: str = "/models"
    MAX_SEQ_LENGTH: int = 512

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()