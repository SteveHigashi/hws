"""Composite indexes for the per-site, time-windowed reads every dashboard page does.

Before this, `events` had single-column indexes on site_id and timestamp only, so a
30-day window for one busy site scanned the whole table (2026-09-19: >200 s and 1.4 GB
for viabandwidth.com's 210k events; the Cloudways host killed the process for it).
"""
from sqlalchemy import inspect, text

REVISION = "003_query_indexes"

INDEXES = (
    ("ix_events_site_ts", "events", "site_id, timestamp"),
    ("ix_events_session_ts", "events", "session_id, timestamp"),
    ("ix_sessions_site_started", "sessions", "site_id, started_at"),
    ("ix_behavior_session_ts", "behavior_events", "session_id, timestamp"),
    ("ix_bot_visits_site_ts", "bot_visits", "site_id, timestamp"),
)


def upgrade(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    for name, table, cols in INDEXES:
        if table not in tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table)}
        if not all(col.strip() in have for col in cols.split(",")):
            continue
        connection.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})"))
