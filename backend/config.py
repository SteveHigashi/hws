from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://higashi:changeme@localhost:5432/higashi"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "changeme_generate_a_real_key"  # replaced at startup, see get_settings
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 30  # 30 days — desktop app stays logged in
    first_run: bool = True
    site_domain: str = ""
    site_name: str = ""
    admin_email: str = ""
    raw_event_retention_days: int = 90
    app_version: str = "0.1.0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    ai_monthly_budget_usd: float = 0.0
    ai_default_model: str = "claude-haiku-4-5-20251001"

    sftp_host: str = ""
    sftp_port: int = 22
    sftp_password: str = ""
    sftp_user_cloudanalyst: str = "log-user"
    sftp_user_stevenhigashi: str = "steve"
    sftp_password_stevenhigashi: str = ""
    sftp_path_stevenhigashi: str = ""

    live_key: str = ""
    live_url: str = "https://intel.cloudanalyst.net"
    live_site_type: str = "other"
    live_ai_stance: str = "search_only"
    live_crawler_version: int = 0

    class Config:
        env_file = ".env"


DEFAULT_SECRET_KEY = "changeme_generate_a_real_key"


def _generated_secret_key() -> str:
    """Create and persist a real SECRET_KEY for installs that never set one.

    The shipped default would let anyone forge admin tokens and would key the
    encryption of saved server logins with a public string.
    """
    import os
    import secrets
    key = secrets.token_hex(32)
    env_path = os.environ.get("HIGASHI_ENV_PATH")
    if env_path:
        try:
            from dotenv import set_key
            set_key(env_path, "SECRET_KEY", key)
            os.chmod(env_path, 0o600)
        except Exception:
            pass  # still use the random key; logins just reset on restart
    os.environ["SECRET_KEY"] = key
    return key


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.secret_key == DEFAULT_SECRET_KEY:
        s.secret_key = _generated_secret_key()
    return s
