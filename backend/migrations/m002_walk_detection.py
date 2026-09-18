"""Create the removable layer-2 detection-run table."""


REVISION = "002_walk_detection"


def upgrade(connection) -> None:
    try:
        from models.walk_detection import WalkDetectionRun
    except ImportError:
        return
    WalkDetectionRun.__table__.create(connection, checkfirst=True)
