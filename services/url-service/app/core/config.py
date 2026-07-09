from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    MODEL_PATH: str = "models/graphsage.pt"
    REDIS_URL: str = "redis://localhost:6379"
    MAX_REDIRECT_HOPS: int = 10
    CRAWLER_TIMEOUT_MS: int = 5000
    WHOIS_CACHE_TTL: int = 86400

    class Config:
        env_file = ".env"

settings = Settings()