from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt as _bcrypt
from pydantic import BaseModel

from database import get_db
from models.user import User, UserRole
from models.site import Site
from config import get_settings
from services.app_config import (
    PUBLIC_URL_KEY,
    SNIPPET_MODE_KEY,
    build_snippet_for,
    normalize_public_url,
    probe_snippet_mode,
    set_value,
)

router = APIRouter()
settings = get_settings()


class SetupPayload(BaseModel):
    admin_email: str
    admin_password: str
    site_name: str
    site_domain: str
    public_url: str = ""
    snippet_mode: str = ""  # "clean" | "php" | "" (caller can pre-fill from probe)
    timezone: str = "UTC"


class ProbePayload(BaseModel):
    public_url: str


@router.post("/probe")
async def probe(payload: ProbePayload):
    """Probe a public URL to decide snippet format. Does not persist anything."""
    url = normalize_public_url(payload.public_url)
    if not url:
        raise HTTPException(status_code=400, detail="Public URL is required")
    mode = await probe_snippet_mode(url)
    return {"public_url": url, "snippet_mode": mode, "reachable": mode is not None}


@router.get("/status")
async def setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.role == UserRole.admin))
    admin_exists = result.scalar_one_or_none() is not None
    return {"setup_complete": admin_exists}


@router.post("/initialize")
async def initialize(payload: SetupPayload, db: AsyncSession = Depends(get_db)):
    # Block if already initialized
    result = await db.execute(select(User).where(User.role == UserRole.admin))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Setup already complete")

    # Create admin user
    admin = User(
        email=payload.admin_email,
        password_hash=_bcrypt.hashpw(payload.admin_password.encode(), _bcrypt.gensalt()).decode(),
        role=UserRole.admin,
    )
    db.add(admin)

    # Create site
    site = Site(
        domain=payload.site_domain,
        name=payload.site_name,
        timezone=payload.timezone,
    )
    db.add(site)

    # Persist public URL + snippet mode so every future snippet is absolute.
    public_url = normalize_public_url(payload.public_url)
    if public_url:
        mode = payload.snippet_mode or await probe_snippet_mode(public_url) or "clean"
        await set_value(db, PUBLIC_URL_KEY, public_url)
        await set_value(db, SNIPPET_MODE_KEY, mode)

    await db.commit()

    return {
        "message": "Setup complete",
        "tracker_key": site.tracker_key,
        "tracker_snippet": await build_snippet_for(db, site.tracker_key),
    }
