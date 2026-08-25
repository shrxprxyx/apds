from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ─── Model (doc 4.4) ──────────────────────────────────────
    # RoBERTa-base fine-tuned for adversarial phishing detection
    # Detects: homoglyphs, zero-width chars, AI-generated text,
    #          word-level perturbations (doc 4.4)
    ADVERSARIAL_MODEL_NAME: str = "roberta-base"
    ADVERSARIAL_MODEL_PATH: str = "/models/adversarial/phishing_roberta"
    MODEL_STORE_PATH: str = "/models"
    MAX_SEQ_LENGTH: int = 512

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()