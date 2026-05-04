from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "changeme"
    database_url: str = "sqlite+aiosqlite:///./app.db"
    anthropic_api_key: str = ""
    host: str = "127.0.0.1"
    port: int = 8000

    # Comma-separated list of allowed CORS origins (e.g. "http://localhost:5173,http://localhost:4173").
    allowed_origins: str = "http://localhost:5173,http://localhost:4173"

    log_level: str = "INFO"

    # Equity account used as the offset when posting opening-balance uploads.
    # Defaults to 300102 "Prior Period Net Worth" from the seed Chart of Accounts.
    opening_balance_equity_account_code: int = 300102

    # Claude model applied to all agents; override via env to switch versions.
    anthropic_model: str = "claude-sonnet-4-6"

    # Database connection options
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    # Maximum file upload size in megabytes
    max_upload_size_mb: int = 20

    model_config = {"env_file": Path(__file__).resolve().parents[3] / ".env"}

    @model_validator(mode="after")
    def _check_production_secret(self) -> "Settings":
        if self.app_env == "production" and self.secret_key == "changeme":
            raise ValueError("SECRET_KEY must be set to a non-default value in production")
        return self


settings = Settings()
