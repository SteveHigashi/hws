"""Store each session's traffic-quality verdict on the row.

Until 2026-09-20 the verdict (verified human / likely human / suspicious / ...) was
recomputed from every event in the window on every dashboard read: minutes of regex
per page load on one vCPU. It is now written once, when the session's events land
(tracker POST, behaviour batch, log import) and read back with GROUP BY.
"""
from sqlalchemy import inspect, text

REVISION = "004_session_quality"

_COLUMNS = {
    "traffic_class": "VARCHAR(20)",       # NULL = not yet classified
    "quality_confidence": "FLOAT",
    "quality_reasons": "TEXT",            # JSON list of short reasons
    "quality_at": "TIMESTAMP",
}


def upgrade(connection) -> None:
    inspector = inspect(connection)
    if "sessions" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("sessions")}
    for name, ddl in _COLUMNS.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE sessions ADD COLUMN {name} {ddl}"))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_sessions_site_started_class "
        "ON sessions (site_id, started_at, traffic_class)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_sessions_unclassified "
        "ON sessions (started_at) WHERE traffic_class IS NULL"
    ))
