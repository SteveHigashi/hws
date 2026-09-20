from fastapi import APIRouter, Request, Depends, HTTPException, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

from database import get_db
from models.behavior import BehaviorEvent
from models.session import Session as SessionModel
from models.site import Site
from services.session_quality import classify_and_commit
from routers.auth import get_current_user

router = APIRouter()


def _clean_site_id(site_id):
    """Coerce an incoming string to UUID for SQLAlchemy binding."""
    import uuid as _uuid
    try:
        return _uuid.UUID(site_id) if site_id else None
    except ValueError:
        return None


def _site_filter(site_id, column):
    """Return list of WHERE conditions for optional site_id filtering."""
    return [column == _clean_site_id(site_id)] if site_id else []

VALID_EVENT_TYPES = {
    "click", "select", "scroll_pause", "tab_blur", "tab_focus",
    "form_field", "media", "error", "copy", "print", "external_click",
}


class BehaviorPayload(BaseModel):
    tracker_key: str
    session_id: str
    page_url: str
    event_type: str
    # Position
    x: Optional[int] = None
    y: Optional[int] = None
    x_pct: Optional[int] = None
    y_pct: Optional[int] = None
    # Element
    element_tag: Optional[str] = None
    element_id: Optional[str] = None
    element_class: Optional[str] = None
    element_text: Optional[str] = Field(None, max_length=256)
    href: Optional[str] = None
    # Text selection
    selected_text: Optional[str] = Field(None, max_length=1024)
    # Timing
    duration_ms: Optional[int] = None
    idle_ms: Optional[int] = None
    # Scroll
    scroll_y: Optional[int] = None
    scroll_pct: Optional[int] = None
    # Form
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    field_action: Optional[str] = None
    # Media
    media_src: Optional[str] = None
    media_action: Optional[str] = None
    media_position: Optional[float] = None
    # Error
    error_message: Optional[str] = Field(None, max_length=2048)
    error_source: Optional[str] = None
    error_line: Optional[int] = None


class BehaviorBatch(BaseModel):
    events: List[BehaviorPayload] = Field(..., max_length=50)


@router.post("/batch")
async def collect_behavior_batch(
    batch: BehaviorBatch,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Accept up to 50 behavioral events at once — tracker flushes on idle/unload."""
    if not batch.events:
        response.status_code = 204
        return

    tracker_key = batch.events[0].tracker_key
    site_result = await db.execute(select(Site).where(Site.tracker_key == tracker_key, Site.active == True))
    site = site_result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=403, detail="Invalid tracker key")

    # Track click positions per session to detect rage/dead clicks
    click_positions: dict[str, list] = defaultdict(list)

    to_insert = []
    for ev in batch.events:
        if ev.event_type not in VALID_EVENT_TYPES:
            continue

        is_rage = False
        is_dead = False

        if ev.event_type == "click" and ev.x is not None and ev.y is not None:
            key = ev.session_id
            pos = (ev.x, ev.y)
            recent = click_positions[key]
            # Rage click: 3+ clicks within 30px of same spot
            nearby = [p for p in recent[-5:] if abs(p[0] - pos[0]) < 30 and abs(p[1] - pos[1]) < 30]
            if len(nearby) >= 2:
                is_rage = True
            click_positions[key].append(pos)
            # Dead click: no tag or tag is div/span/p with no href
            if ev.element_tag and ev.element_tag.lower() in ("div", "span", "p", "section", "article") and not ev.href:
                is_dead = True

        to_insert.append(BehaviorEvent(
            site_id=site.id,
            session_id=ev.session_id,
            page_url=ev.page_url,
            event_type=ev.event_type,
            x=ev.x, y=ev.y, x_pct=ev.x_pct, y_pct=ev.y_pct,
            element_tag=ev.element_tag,
            element_id=ev.element_id,
            element_class=ev.element_class,
            element_text=ev.element_text,
            href=ev.href,
            selected_text=ev.selected_text,
            duration_ms=ev.duration_ms,
            idle_ms=ev.idle_ms,
            scroll_y=ev.scroll_y,
            scroll_pct=ev.scroll_pct,
            field_name=ev.field_name,
            field_type=ev.field_type,
            field_action=ev.field_action,
            media_src=ev.media_src,
            media_action=ev.media_action,
            media_position=ev.media_position,
            error_message=ev.error_message,
            error_source=ev.error_source,
            error_line=ev.error_line,
            is_rage_click=is_rage,
            is_dead_click=is_dead,
        ))

    db.add_all(to_insert)
    await db.commit()
    # Behaviour events are JS proof: the session's stored verdict becomes verified_human.
    await classify_and_commit(db, {ev.session_id for ev in to_insert})
    response.status_code = 204
    return


# --- Analytics endpoints ---

def _since(days):
    return datetime.utcnow() - timedelta(days=days)


@router.get("/summary")
async def behavior_summary(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    conds = [BehaviorEvent.timestamp >= s, *_site_filter(site_id, BehaviorEvent.site_id)]
    result = await db.execute(
        select(BehaviorEvent.event_type, func.count(BehaviorEvent.id).label("count"))
        .where(*conds)
        .group_by(BehaviorEvent.event_type)
        .order_by(desc("count"))
    )
    return [{"type": r.event_type, "count": r.count} for r in result]


@router.get("/rage-clicks")
async def rage_clicks(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    conds = [BehaviorEvent.timestamp >= s, BehaviorEvent.is_rage_click == True,
             *_site_filter(site_id, BehaviorEvent.site_id)]
    result = await db.execute(
        select(BehaviorEvent.page_url, func.count(BehaviorEvent.id).label("count"))
        .where(*conds)
        .group_by(BehaviorEvent.page_url)
        .order_by(desc("count"))
        .limit(limit)
    )
    return [{"page": r.page_url, "rage_clicks": r.count} for r in result]


@router.get("/dead-clicks")
async def dead_clicks(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    conds = [BehaviorEvent.timestamp >= s, BehaviorEvent.is_dead_click == True,
             *_site_filter(site_id, BehaviorEvent.site_id)]
    result = await db.execute(
        select(
            BehaviorEvent.page_url,
            BehaviorEvent.element_tag,
            BehaviorEvent.element_text,
            func.count(BehaviorEvent.id).label("count"),
        )
        .where(*conds)
        .group_by(BehaviorEvent.page_url, BehaviorEvent.element_tag, BehaviorEvent.element_text)
        .order_by(desc("count"))
        .limit(limit)
    )
    return [{"page": r.page_url, "element": r.element_tag, "text": r.element_text, "count": r.count} for r in result]


@router.get("/selected-text")
async def selected_text(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    result = await db.execute(
        select(BehaviorEvent.selected_text, func.count(BehaviorEvent.id).label("count"))
        .where(
            BehaviorEvent.timestamp >= s,
            BehaviorEvent.event_type == "select",
            BehaviorEvent.selected_text.isnot(None),
            *_site_filter(site_id, BehaviorEvent.site_id),
        )
        .group_by(BehaviorEvent.selected_text)
        .order_by(desc("count"))
        .limit(limit)
    )
    return [{"text": r.selected_text, "count": r.count} for r in result]


@router.get("/scroll-attention")
async def scroll_attention(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Scroll pause zones — where visitors stop and read."""
    s = _since(days)
    result = await db.execute(
        select(
            BehaviorEvent.page_url,
            BehaviorEvent.scroll_pct,
            func.count(BehaviorEvent.id).label("pauses"),
            func.avg(BehaviorEvent.duration_ms).label("avg_pause_ms"),
        )
        .where(
            BehaviorEvent.timestamp >= s,
            BehaviorEvent.event_type == "scroll_pause",
            BehaviorEvent.scroll_pct.isnot(None),
            *_site_filter(site_id, BehaviorEvent.site_id),
        )
        .group_by(BehaviorEvent.page_url, BehaviorEvent.scroll_pct)
        .order_by(BehaviorEvent.page_url, BehaviorEvent.scroll_pct)
    )
    # Group by page
    pages: dict = {}
    for r in result:
        path = _short_path(r.page_url)
        if path not in pages:
            pages[path] = []
        pages[path].append({
            "scroll_pct": r.scroll_pct,
            "pauses": r.pauses,
            "avg_pause_ms": round(float(r.avg_pause_ms)) if r.avg_pause_ms else None,
        })
    return [{"page": k, "zones": v} for k, v in pages.items()]


@router.get("/form-abandonment")
async def form_abandonment(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    result = await db.execute(
        select(
            BehaviorEvent.page_url,
            BehaviorEvent.field_name,
            BehaviorEvent.field_type,
            func.count(BehaviorEvent.id).label("abandons"),
        )
        .where(
            BehaviorEvent.timestamp >= s,
            BehaviorEvent.event_type == "form_field",
            BehaviorEvent.field_action == "abandon",
            *_site_filter(site_id, BehaviorEvent.site_id),
        )
        .group_by(BehaviorEvent.page_url, BehaviorEvent.field_name, BehaviorEvent.field_type)
        .order_by(desc("abandons"))
        .limit(20)
    )
    return [{"page": r.page_url, "field": r.field_name, "type": r.field_type, "abandons": r.abandons} for r in result]


@router.get("/errors")
async def js_errors(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    result = await db.execute(
        select(
            BehaviorEvent.error_message,
            BehaviorEvent.error_source,
            BehaviorEvent.page_url,
            func.count(BehaviorEvent.id).label("count"),
        )
        .where(BehaviorEvent.timestamp >= s, BehaviorEvent.event_type == "error",
               *_site_filter(site_id, BehaviorEvent.site_id))
        .group_by(BehaviorEvent.error_message, BehaviorEvent.error_source, BehaviorEvent.page_url)
        .order_by(desc("count"))
        .limit(20)
    )
    return [{"message": r.error_message, "source": r.error_source, "page": r.page_url, "count": r.count} for r in result]


@router.get("/external-clicks")
async def external_clicks(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    s = _since(days)
    result = await db.execute(
        select(BehaviorEvent.href, func.count(BehaviorEvent.id).label("clicks"))
        .where(
            BehaviorEvent.timestamp >= s,
            BehaviorEvent.event_type == "external_click",
            BehaviorEvent.href.isnot(None),
            *_site_filter(site_id, BehaviorEvent.site_id),
        )
        .group_by(BehaviorEvent.href)
        .order_by(desc("clicks"))
        .limit(20)
    )
    return [{"url": r.href, "clicks": r.clicks} for r in result]


# ---------------------------------------------------------------------------
# Composite "story" indices — single-number narratives over the period
# ---------------------------------------------------------------------------

# Behaviors that indicate active reading engagement
_READING_INTENT_TYPES = {"select", "copy"}


@router.get("/indices")
async def behavior_indices(
    days: int = Query(30, ge=1, le=90),
    site_id: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Three composite indices that summarise how visitors *feel* and *behave*
    in aggregate — not the raw events the rest of this router exposes.

    - frustration_index   :: (rage + dead + js_errors) per 100 sessions
    - reading_intent_pct  :: % of sessions with a select/copy or deep scroll
    - silent_audience_pct :: % of sessions with zero behavioural events
                             (pure readers — they don't click anything)
    """
    s = _since(days)
    site_be = _site_filter(site_id, BehaviorEvent.site_id)
    site_sess = _site_filter(site_id, SessionModel.site_id)

    # Sessions in window — the denominator for everything
    total_sessions = (await db.execute(
        select(func.count(SessionModel.id)).where(SessionModel.started_at >= s, *site_sess)
    )).scalar() or 0

    # Frustration components
    rage = (await db.execute(
        select(func.count(BehaviorEvent.id)).where(
            BehaviorEvent.timestamp >= s, BehaviorEvent.is_rage_click == True, *site_be,
        )
    )).scalar() or 0
    dead = (await db.execute(
        select(func.count(BehaviorEvent.id)).where(
            BehaviorEvent.timestamp >= s, BehaviorEvent.is_dead_click == True, *site_be,
        )
    )).scalar() or 0
    errors = (await db.execute(
        select(func.count(BehaviorEvent.id)).where(
            BehaviorEvent.timestamp >= s, BehaviorEvent.event_type == "error", *site_be,
        )
    )).scalar() or 0

    frustration_per_100 = (
        round((rage + dead + errors) / total_sessions * 100, 2) if total_sessions else 0.0
    )

    # Reading-intent sessions: at least one selection/copy OR a deep scroll pause
    reading_sids = (await db.execute(
        select(func.count(func.distinct(BehaviorEvent.session_id))).where(
            BehaviorEvent.timestamp >= s,
            *site_be,
            or_(
                BehaviorEvent.event_type.in_(_READING_INTENT_TYPES),
                and_(BehaviorEvent.event_type == "scroll_pause",
                     BehaviorEvent.scroll_pct >= 75),
            ),
        )
    )).scalar() or 0
    reading_pct = (
        round(reading_sids / total_sessions * 100, 1) if total_sessions else 0.0
    )

    # Silent: sessions with NO behaviour rows at all
    sessions_with_behavior = (await db.execute(
        select(func.count(func.distinct(BehaviorEvent.session_id))).where(
            BehaviorEvent.timestamp >= s, *site_be,
        )
    )).scalar() or 0
    silent_pct = (
        round((total_sessions - sessions_with_behavior) / total_sessions * 100, 1)
        if total_sessions else 0.0
    )

    return {
        "days": days,
        "total_sessions": total_sessions,
        "frustration_index": frustration_per_100,
        "frustration_components": {"rage": rage, "dead": dead, "errors": errors},
        "reading_intent_pct": reading_pct,
        "reading_intent_sessions": reading_sids,
        "silent_audience_pct": silent_pct,
        "sessions_with_behavior": sessions_with_behavior,
    }


def _short_path(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).path or url
    except Exception:
        return url
