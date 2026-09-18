from sqlalchemy import Column, String, DateTime, Integer, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    entry_page = Column(String(1024), nullable=True)
    exit_page = Column(String(1024), nullable=True)
    page_count = Column(Integer, default=1)
    duration_seconds = Column(Float, nullable=True)

    is_bounce = Column(Boolean, default=True)
    is_returning = Column(Boolean, default=False)

    country = Column(String(2), nullable=True)
    device_type = Column(String(32), nullable=True)
    referrer_domain = Column(String(256), nullable=True)

    utm_source = Column(String(256), nullable=True)
    utm_medium = Column(String(256), nullable=True)
    utm_campaign = Column(String(256), nullable=True)
