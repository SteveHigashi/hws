import uuid
from sqlalchemy import Column, String, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.sql import func
from database import Base


class ImportCursor(Base):
    __tablename__ = "import_cursors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id = Column(String(36), nullable=False)
    log_path = Column(Text, nullable=False)
    last_line_at = Column(DateTime(timezone=True), nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    total_imported = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("site_id", "log_path", name="uq_cursor_site_path"),)
