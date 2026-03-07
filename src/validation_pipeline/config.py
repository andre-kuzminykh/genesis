from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/validation"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/validation"
    environment: str = "dev"
    log_level: str = "INFO"

    # Scoring thresholds
    low_confidence_threshold: float = 0.4
    proceed_threshold: float = 0.7
    iterate_threshold: float = 0.4

    model_config = {"env_prefix": "VP_"}


settings = Settings()
