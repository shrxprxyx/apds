from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ─── Model (doc 4.3.1) ────────────────────────────────────
    # EfficientNet-B3 feature extractor
    # FAISS index for brand similarity search
    VISUAL_MODEL_PATH: str = "/models/visual/efficientnet_brand"
    BRAND_INDEX_PATH: str = "/models/visual/brand_index.faiss"
    BRAND_LABELS_PATH: str = "/models/visual/brand_labels.json"
    MODEL_STORE_PATH: str = "/models"

    # ─── Screenshot (doc 4.3.1) ───────────────────────────────
    # Playwright headless Chromium, 2s timeout per doc
    SCREENSHOT_TIMEOUT_MS: int = 2000
    SCREENSHOT_WIDTH: int = 1280
    SCREENSHOT_HEIGHT: int = 800

    # ─── FAISS (doc 4.3.2) ────────────────────────────────────
    # Cosine similarity threshold for brand match
    BRAND_SIMILARITY_THRESHOLD: float = 0.85
    TOP_K_BRANDS: int = 3

    # ─── MinIO ────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "apds_minio"
    MINIO_SECRET_KEY: str = "changeme_minio"
    MINIO_BUCKET_SCREENSHOTS: str = "apds-screenshots"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()