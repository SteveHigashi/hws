"""Idempotent migration runner used after SQLAlchemy's create_all."""

from migrations.m001_bot_verification import upgrade as upgrade_bot_verification


def apply_migrations(connection) -> None:
    upgrade_bot_verification(connection)
    try:
        from migrations.m002_walk_detection import upgrade as upgrade_walk_detection
    except ImportError:
        return
    upgrade_walk_detection(connection)
    try:
        from migrations.m003_query_indexes import upgrade as upgrade_query_indexes
    except ImportError:
        return
    upgrade_query_indexes(connection)
    try:
        from migrations.m004_session_quality import upgrade as upgrade_session_quality
    except ImportError:
        return
    upgrade_session_quality(connection)
    try:
        from migrations.m005_live_reading_recommendation import upgrade as upgrade_live_reading_recommendation
    except ImportError:
        return
    upgrade_live_reading_recommendation(connection)
