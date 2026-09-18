"""Read/write persisted app-level config (public URL, snippet mode).

These values are set during the first-run wizard and used everywhere a
tracker snippet is generated.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from models.app_setting import AppSetting


PUBLIC_URL_KEY = "public_url"
SNIPPET_MODE_KEY = "snippet_mode"  # "clean" | "php"


async def get_value(db: AsyncSession, key: str) -> str | None:
    r = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = r.scalar_one_or_none()
    return row.value if row else None


async def set_value(db: AsyncSession, key: str, value: str | None) -> None:
    r = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = r.scalar_one_or_none()
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


def normalize_public_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


async def probe_snippet_mode(public_url: str) -> str | None:
    """Return "clean" | "php" | None.

    Probes the public URL to decide which endpoint format the snippet should
    use. None means neither responded — the caller should treat the URL as
    unreachable.
    """
    base = normalize_public_url(public_url)
    if not base:
        return None
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        # Prefer clean URLs if the backend itself is reachable at the public URL.
        try:
            r = await client.get(f"{base}/api/health")
            if r.status_code == 200:
                return "clean"
        except Exception:
            pass
        # Fall back to PHP proxy (managed hosting like Cloudways).
        try:
            r = await client.get(f"{base}/api/collect/pageview.php", params={"k": "_probe"})
            # The proxy returns 4xx for bad keys but proves PHP routing works.
            if r.status_code < 500:
                return "php"
        except Exception:
            pass
    return None


def build_snippet(tracker_key: str, public_url: str | None, snippet_mode: str | None) -> str:
    """Generate the universal absolute-URL tracker snippet."""
    base = normalize_public_url(public_url) if public_url else ""
    if not base:
        # No public URL configured yet — fall back to relative (works for desktop/local).
        return f'<script src="/tracker.js" data-key="{tracker_key}" async></script>'

    src = f"{base}/tracker.js"
    if snippet_mode == "php":
        pageview = f"{base}/api/collect/pageview.php"
        behavior = f"{base}/api/behavior/batch.php"
        return (
            f'<script src="{src}" data-key="{tracker_key}" '
            f'data-pageview-api="{pageview}" data-behavior-api="{behavior}" async></script>'
        )
    # "clean" or unknown — use api-base, tracker.js builds endpoints itself.
    return f'<script src="{src}" data-key="{tracker_key}" data-api-base="{base}" async></script>'


async def build_snippet_for(db: AsyncSession, tracker_key: str) -> str:
    public_url = await get_value(db, PUBLIC_URL_KEY)
    snippet_mode = await get_value(db, SNIPPET_MODE_KEY)
    return build_snippet(tracker_key, public_url, snippet_mode)
