from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "local"
    app_url: str = "http://127.0.0.1:8000"
    frontend_url: str = "http://localhost:5173"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 720
    refresh_token_expire_days: int = 14
    session_cookie_name: str = "eg_session"
    csrf_cookie_name: str = "eg_csrf"
    refresh_cookie_name: str = "eg_refresh"
    database_url: str = "sqlite:///./experiencegraph_enterprise.db"
    openai_api_key: str | None = None
    embedding_provider: str = "auto"
    embedding_index_path: str = "data/embedding_index.json"
    embedding_similarity_limit: int = 5
    storage_backend: str = "firebase"
    firebase_project_id: str | None = None
    firebase_credentials_path: str | None = None
    firebase_credentials_json: str | None = None
    firebase_cases_collection: str = "cases"
    firebase_users_collection: str = "users"
    firebase_audit_collection: str = "audit_logs"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "experiencegraph_cases"
    hybrid_vector_weight: float = 0.5
    hybrid_keyword_weight: float = 0.2
    hybrid_fuzzy_weight: float = 0.1
    hybrid_tag_weight: float = 0.1
    hybrid_constraint_weight: float = 0.05
    hybrid_specialty_weight: float = 0.05
    endorsement_daily_limit: int = 10
    login_rate_limit_window_minutes: int = 15
    login_rate_limit_max_attempts: int = 8
    jwt_algorithm: str = "HS256"
    bootstrap_schema: bool = True
    demo_super_admin_email: str | None = "superadmin@demo.health"
    default_retention_days: int = 365

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
