from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "ExperienceGraph"
    environment: str = "local"
    secret_key: str = "change-this-secret"
    access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./experiencegraph.sqlite3"
    openai_api_key: str | None = None
    embeddings_model: str = "text-embedding-3-small"
    embeddings_backend: str = "auto"
    allow_signup: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
