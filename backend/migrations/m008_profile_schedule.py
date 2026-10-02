"""Add import schedules to saved log sources."""
from sqlalchemy import inspect, text

REVISION = "008_profile_schedule"


def upgrade(connection) -> None:
    inspector = inspect(connection)
    if "pull_profiles" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("pull_profiles")}
    if "schedule" not in existing:
        connection.execute(text("ALTER TABLE pull_profiles ADD COLUMN schedule VARCHAR(16) NOT NULL DEFAULT 'off'"))
    if "last_run_at" not in existing:
        connection.execute(text("ALTER TABLE pull_profiles ADD COLUMN last_run_at TIMESTAMP"))
