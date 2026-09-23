"""WebAuthn credentials for optional passkey sign-in."""
from sqlalchemy import inspect, text

REVISION = "007_passkeys"


def upgrade(connection) -> None:
    inspector = inspect(connection)
    if "passkeys" in inspector.get_table_names():
        return
    connection.execute(text(
        "CREATE TABLE passkeys ("
        " id CHAR(32) PRIMARY KEY,"
        " user_id CHAR(32) NOT NULL,"
        " credential_id BLOB NOT NULL UNIQUE,"
        " public_key BLOB NOT NULL,"
        " sign_count INTEGER NOT NULL DEFAULT 0,"
        " transports TEXT NULL,"
        " name VARCHAR(120) NULL,"
        " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        " last_used_at TIMESTAMP NULL)"
    ))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_passkeys_user_id ON passkeys (user_id)"))
