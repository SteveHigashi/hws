from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from collections import defaultdict
from models.event import Event


async def get_session_paths(db: AsyncSession, site_id, days: int = 30, min_weight: int = 2):
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(Event.session_id, Event.page_url, Event.timestamp)
        .where(Event.site_id == site_id, Event.timestamp >= since, Event.is_bot == False)
        .order_by(Event.session_id, Event.timestamp)
    )
    rows = result.all()

    # Group events by session
    sessions = defaultdict(list)
    for row in rows:
        sessions[row.session_id].append(row.page_url)

    # Build transition counts
    transitions = defaultdict(int)
    for pages in sessions.values():
        for i in range(len(pages) - 1):
            src = _short_path(pages[i])
            dst = _short_path(pages[i + 1])
            if src != dst:
                transitions[(src, dst)] += 1

    # Resolve cycles: for each undirected pair keep only the dominant direction
    dominant = {}
    for (src, dst), weight in transitions.items():
        key = tuple(sorted([src, dst]))
        if key not in dominant or weight > dominant[key][1]:
            dominant[key] = ((src, dst), weight)

    # Format as Sankey nodes + links
    node_set = set()
    links = []
    for (src, dst), weight in dominant.values():
        if weight >= min_weight:
            node_set.add(src)
            node_set.add(dst)
            links.append({"source": src, "target": dst, "value": weight})

    nodes = [{"id": n} for n in sorted(node_set)]
    links.sort(key=lambda x: x["value"], reverse=True)

    return {"nodes": nodes, "links": links[:50]}  # cap at 50 flows


def _short_path(url: str) -> str:
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path
        return path if path else "/"
    except Exception:
        return url
