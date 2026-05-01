from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "changeme"
    database_url: str = "sqlite+aiosqlite:///./app.db"
    anthropic_api_key: str = ""
    host: str = "127.0.0.1"
    port: int = 8000

    log_level: str = "INFO"

    # Equity account used as the offset when posting opening-balance uploads.
    # Defaults to 300102 "Prior Period Net Worth" from the seed Chart of Accounts.
    opening_balance_equity_account_code: int = 300102

    model_config = {"env_file": ".env"}


settings = Settings()
