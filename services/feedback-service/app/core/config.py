from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    REDIS_URL: str

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
