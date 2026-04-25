from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "changeme"
    database_url: str = "sqlite+aiosqlite:///./app.db"
    anthropic_api_key: str = ""
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = {"env_file": ".env"}


settings = Settings()
