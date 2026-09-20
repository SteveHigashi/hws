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

    # viabandwidth.com lives on its own IONOS VPS (plain nginx, not Cloudways)
    ssh_password_viabandwidth: str = ""
    live_key: str = ""
    # Who writes the walk reading shown on the dashboard: "local" = the fixed rules on
    # this install (free), "byok" = the same prompt through the customer's own model key
    # (still local), "live" = Higashi Live's stored reading. Rules are the ceiling in all three.
    walk_reading_provider: str = "local"
    walk_reading_model: str = ""   # BYOK model id; empty = ai_default_model
    live_url: str = "https://intel.cloudanalyst.net"
    live_site_type: str = "other"
    live_ai_stance: str = "search_only"
    live_stance: str = ""   # five-way stance (higashi_reading.crawlers.STANCES); empty = meaning of live_ai_stance
    live_crawler_version: int = 0

    class Config:
        env_file = ".env"


def env_file_path() -> str:
    """The ONE settings file: what get_settings() reads and what the admin UI
    and secret-key persistence write.

    Before 2026-09-18 these disagreed. The loader always read ./.env while the
    writers used HIGASHI_ENV_PATH, so on any install that set the variable
    (the desktop launcher, passenger_wsgi, the cloudanalyst start.sh) a key
    saved through the admin UI landed in a file the running process never
    opened, and the UI reported it saved. Resolved here once, read everywhere.
    """
    import os
    return os.environ.get("HIGASHI_ENV_PATH") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".env")


DEFAULT_SECRET_KEY = "changeme_generate_a_real_key"


def _generated_secret_key() -> str:
    """Create and persist a real SECRET_KEY for installs that never set one.

    The shipped default would let anyone forge admin tokens and would key the
    encryption of saved server logins with a public string.
    """
    import os
    import secrets
    key = secrets.token_hex(32)
    try:
        from dotenv import set_key
        set_key(env_file_path(), "SECRET_KEY", key)
        os.chmod(env_file_path(), 0o600)
    except Exception:
        pass  # still use the random key; logins just reset on restart
    os.environ["SECRET_KEY"] = key
    return key


@lru_cache
def get_settings() -> Settings:
    s = Settings(_env_file=env_file_path())
    if s.secret_key == DEFAULT_SECRET_KEY:
        s.secret_key = _generated_secret_key()
    return s
