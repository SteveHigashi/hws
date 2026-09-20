"""One-time password reset tokens (hash only) for the sign-in reset path."""
from sqlalchemy import inspect, text

REVISION = "006_password_resets"


def upgrade(connection) -> None:
    inspector = inspect(connection)
    if "password_resets" in inspector.get_table_names():
        return
    connection.execute(text(
        "CREATE TABLE password_resets ("
        " id CHAR(32) PRIMARY KEY,"
        " user_id CHAR(32) NOT NULL,"
        " token_hash VARCHAR(64) NOT NULL UNIQUE,"
        " expires_at TIMESTAMP NOT NULL,"
        " used_at TIMESTAMP NULL,"
        " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_password_resets_user_id ON password_resets (user_id)"))
