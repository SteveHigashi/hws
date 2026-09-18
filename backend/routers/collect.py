from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import Response as FastResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import base64
import hashlib
import re

from database import get_db
from models.event import Event
from models.session import Session
from models.site import Site
from models.bot_visit import BotVisit
from services.geo import resolve_geo
from services.bot import classify_bot
from services.deception import analyze as analyze_deception

# 1×1 transparent GIF — returned for every pixel request
_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

router = APIRouter()


class PageViewPayload(BaseModel):
    tracker_key: str
    session_id: str
    page_url: str
    page_title: Optional[str] = None
    referrer: Optional[str] = None
    screen_width: Optional[int] = None
    screen_height: Optional[int] = None
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    scroll_depth: Optional[int] = None
    lcp: Optional[float] = None
    fcp: Optional[float] = None
    ttfb: Optional[float] = None
    is_404: Optional[bool] = False
    # UTM — tracker parses from URL and sends explicitly
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    anchor: Optional[str] = None


@router.post("/pageview")
async def collect_pageview(
    payload: PageViewPayload,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Site).where(Site.tracker_key == payload.tracker_key, Site.active == True))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=403, detail="Invalid tracker key")

    user_agent = request.headers.get("user-agent", "")
    client_ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()

    bot = classify_bot(user_agent, client_ip)
    if bot:
        db.add(BotVisit(
            site_id=site.id,
            page_path=(urlparse(payload.page_url).path or "/")[:2048],
            bot_name=bot["name"],
            bot_category=bot["category"],
            user_agent=user_agent[:1024],
            verification_state=bot["verification_state"],
            verification_method=bot["verification_method"],
            ip_hash=hashlib.sha256(f"{client_ip}{site.id}".encode()).hexdigest(),
            referrer=payload.referrer,
        ))
        await db.commit()
        response.status_code = 204
        return

    # Honest crawlers are gone by here. What remains may still be a bot that
    # LIES — a fabricated user-agent, a consumer browser arriving from cloud
    # server space, or a forged search referral. classify_bot() cannot see those
    # because it matches on names, and these carry no bot name at all.
    #
    # Recording them as human is the failure mode this catches: it silently
    # inflates visitor counts and pollutes referrer reporting with fake organic
    # search. They go to BotVisit with the reason attached, so the dashboard can
    # show WHY something was judged non-human rather than just asserting it.
    deception = analyze_deception(user_agent, client_ip, payload.referrer)
    if deception["deceptive"] and deception["confidence"] in ("high", "medium"):
        geo = await resolve_geo(client_ip)
        db.add(BotVisit(
            site_id=site.id,
            page_path=(urlparse(payload.page_url).path or "/")[:2048],
            bot_name=(deception["signals"][0] if deception["signals"] else "deceptive")[:64],
            bot_category="deceptive",
            country=geo.get("country"),
            user_agent=user_agent[:1024],
            verification_state="unverified",
            ip_hash=hashlib.sha256(f"{client_ip}{site.id}".encode()).hexdigest(),
            referrer=payload.referrer,
        ))
        await db.commit()
        response.status_code = 204
        return

    ip_hash = hashlib.sha256(f"{client_ip}{site.id}".encode()).hexdigest()
    geo = await resolve_geo(client_ip)

    from user_agents import parse as parse_ua
    ua = parse_ua(user_agent)
    device_type = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"

    # Extract search query from referrer (Google, Bing pass it)
    search_query = _extract_search_query(payload.referrer)

    # Upsert session
    sess_result = await db.execute(select(Session).where(Session.id == payload.session_id))
    session = sess_result.scalar_one_or_none()

    if not session:
        session = Session(
            id=payload.session_id,
            site_id=site.id,
            entry_page=payload.page_url,
            country=geo.get("country"),
            device_type=device_type,
            referrer_domain=_extract_domain(payload.referrer),
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
        )
        db.add(session)
    else:
        session.page_count += 1
        session.is_bounce = False
        session.exit_page = payload.page_url
        session.last_seen_at = datetime.utcnow()

    event = Event(
        site_id=site.id,
        session_id=payload.session_id,
        page_url=payload.page_url,
        page_title=payload.page_title,
        referrer=payload.referrer,
        ip_hash=ip_hash,
        country=geo.get("country"),
        region=geo.get("region"),
        city=geo.get("city"),
        asn=geo.get("asn"),
        timezone=geo.get("timezone"),
        browser=ua.browser.family,
        browser_version=ua.browser.version_string,
        os=ua.os.family,
        device_type=device_type,
        screen_width=payload.screen_width,
        screen_height=payload.screen_height,
        language=payload.language,
        user_agent=user_agent,
        duration_seconds=payload.duration_seconds,
        scroll_depth=payload.scroll_depth,
        lcp=payload.lcp,
        fcp=payload.fcp,
        ttfb=payload.ttfb,
        is_bot=False,
        is_404=payload.is_404 or False,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_content=payload.utm_content,
        utm_term=payload.utm_term,
        anchor=payload.anchor,
        search_query=search_query,
    )
    db.add(event)
    await db.commit()

    response.status_code = 204
    return


@router.get("/pixel")
async def tracking_pixel(
    k: str,
    p: Optional[str] = "/",
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    1×1 tracking pixel — captures AI crawler and bot visits.
    Site owners add <img src="/collect/pixel?k=KEY&p=/page"> to their HTML.
    JavaScript trackers handle humans; this endpoint handles crawlers.
    """
    result = await db.execute(select(Site).where(Site.tracker_key == k, Site.active == True))
    site = result.scalar_one_or_none()

    if site:
        ua = request.headers.get("user-agent", "")
        client_ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
        bot = classify_bot(ua, client_ip)
        if bot:
            geo = await resolve_geo(client_ip)
            db.add(BotVisit(
                site_id=site.id,
                page_path=(p or "/")[:2048],
                bot_name=bot["name"],
                bot_category=bot["category"],
                country=geo.get("country"),
                user_agent=ua[:1024],
                verification_state=bot["verification_state"],
                verification_method=bot["verification_method"],
                ip_hash=hashlib.sha256(f"{client_ip}{site.id}".encode()).hexdigest(),
            ))
            await db.commit()

    return FastResponse(
        content=_PIXEL_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


def _extract_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return urlparse(url).netloc
    except Exception:
        return None


def _extract_search_query(referrer: Optional[str]) -> Optional[str]:
    if not referrer:
        return None
    try:
        parsed = urlparse(referrer)
        params = parse_qs(parsed.query)
        # Google uses 'q', Bing uses 'q', Yahoo uses 'p'
        for key in ("q", "p", "query"):
            if key in params:
                return params[key][0][:512]
    except Exception:
        pass
    return None
