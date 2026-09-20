from sqlalchemy import Column, String, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class LiveReading(Base):
    """A reading Higashi Live returned for a bundle this install sent it."""

    __tablename__ = "live_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    live_reading_id = Column(Integer, nullable=True)
    headline = Column(String(512), nullable=False)
    paragraphs = Column(JSON, nullable=False, default=list)
    verdict = Column(String(256), nullable=False)
    changes = Column(JSON, nullable=False, default=list)
    benchmarks = Column(JSON, nullable=False, default=list)
    recommendation = Column(JSON, nullable=True)  # m005
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
