from pydantic_settings import BaseSettings
from functools import lru_cache


def _version_from_file() -> str:
    """The version in the VERSION file beside the install, or a dev marker."""
    import pathlib as _p
    for candidate in (_p.Path(__file__).resolve().parent.parent / "VERSION",):
        try:
            text = candidate.read_text().strip()
            if text:
                return text
        except OSError:
            pass
    return "0.0.0-dev"


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://higashi:changeme@localhost:5432/higashi"
    secret_key: str = "changeme_generate_a_real_key"  # replaced at startup, see get_settings
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 30  # 30 days — desktop app stays logged in
    first_run: bool = True
    site_domain: str = ""
    dashboard_url: str = ""   # where the dashboard is served; site_domain is a tracked site, not this
    site_name: str = ""
    admin_email: str = ""
    raw_event_retention_days: int = 90
    # Read from the VERSION file the release ships, so an install can name its
    # own build. It said 0.1.0 while release 0.2.3 was running, which is the
    # same defect JDrive had: a box that cannot state what it is makes every
    # support conversation start with a guess.
    app_version: str = _version_from_file()

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    ai_monthly_budget_usd: float = 0.0
    ai_default_model: str = "claude-haiku-4-5-20251001"

    # Optional: pull access logs from another server over SSH/SFTP instead of, or as
    # well as, using the browser tracker. Configure your own sources with LOG_SOURCES
    # (see .env.example); these are the shared connection defaults.
    sftp_host: str = ""
    sftp_port: int = 22
    sftp_user: str = ""
    sftp_password: str = ""

    # Semicolon-separated log sources, each "label|domain|/path/to/access.log" and
    # optionally "|user|password" when that source needs its own credentials.
    # Empty means manual upload only.
    log_sources: str = ""
    live_key: str = ""
    # Who writes the walk reading shown on the dashboard: "local" = the fixed rules on
    # this install (free), "byok" = the same prompt through the customer's own model key
    # (still local), "live" = Higashi Live's stored reading. Rules are the ceiling in all three.
    walk_reading_provider: str = "local"
    walk_reading_model: str = ""   # BYOK model id; empty = ai_default_model
    live_url: str = "https://live.hws.jotnotes.com"

    # External IP geolocation. OFF by default, and it must stay off by default.
    #
    # When this is "on", every visitor IP seen by the log importer and by the
    # browser collector is sent to ip-api.com - a third party, in the United
    # States, over plain HTTP, because the free tier offers no TLS. An IP address
    # is personal data. Higashi is sold and documented as self-hosted analytics
    # that keeps a customer's data on their own server, so this cannot be the
    # default and cannot be silent.
    #
    # Turning it on is the operator's informed choice, made in their own
    # settings.env. Nothing else in Higashi contacts a third party.
    #
    # This is NOT covered by any research or product-improvement consent, and
    # must never be bundled with one: that consent is about sharing data with
    # JotNotes, this is about sending visitor IPs to an unrelated company.
    external_geo: bool = False

    # Voluntary research sharing. OFF by default, and it must stay off by default.
    #
    # When an operator deliberately turns this on, Higashi sends the aggregate
    # figures it has ALREADY derived for the dashboard - crawler counts, session
    # and pageview totals, the walk verdict - so JotNotes can improve Higashi and
    # Higashi Live, improve detection, study trends, and publish aggregate
    # industry research, reports and white papers.
    #
    # It is NOT the Live service and must never be enabled by any of: installing
    # Higashi, buying Live, entering a Live key, or configuring Live. It needs no
    # Live key and works for operators who have never bought anything. It carries
    # no raw visitor IPs, URLs, paths, user agents, credentials or logs.
    research_sharing: bool = False

    # Same host as Live, a different path. The infrastructure is shared; the two
    # are separate code paths, separate settings and separate endpoints, so that
    # turning one on can never turn the other on.
    research_url: str = "https://live.hws.jotnotes.com"
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
