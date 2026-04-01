from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://skp:skp@127.0.0.1:5433/skp"
    redis_url: str = "redis://127.0.0.1:6380/0"

    jwt_secret: str = "dev-only-change-in-production"
    jwt_issuer: str = "sovereign-knowledge-platform"
    jwt_access_token_expire_minutes: int = 60


settings = Settings()
