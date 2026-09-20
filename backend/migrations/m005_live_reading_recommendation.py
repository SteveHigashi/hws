"""Keep the structured recommendation that comes back with a Live reading."""
from sqlalchemy import inspect, text

REVISION = "005_live_reading_recommendation"


def upgrade(connection) -> None:
    inspector = inspect(connection)
    if "live_readings" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("live_readings")}
    if "recommendation" not in existing:
        connection.execute(text("ALTER TABLE live_readings ADD COLUMN recommendation JSON"))
