"""Persist import-time network verdicts without retaining raw addresses."""

from sqlalchemy import inspect, text


REVISION = "001_bot_verification"

_COLUMNS = {
    "verification_state": "VARCHAR(16) NOT NULL DEFAULT 'unverified'",
    "verification_method": "VARCHAR(32)",
    "ip_hash": "VARCHAR(64)",
    "http_status": "INTEGER",
    "response_bytes": "INTEGER",
    "referrer": "TEXT",
}


def upgrade(connection) -> None:
    inspector = inspect(connection)
    if "bot_visits" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("bot_visits")}
    for name, ddl in _COLUMNS.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE bot_visits ADD COLUMN {name} {ddl}"))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_bot_visits_verification_state "
        "ON bot_visits (verification_state)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_bot_visits_ip_hash ON bot_visits (ip_hash)"
    ))
