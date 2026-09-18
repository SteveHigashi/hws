from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Page
    page_url = Column(Text, nullable=False)
    page_title = Column(String(512), nullable=True)
    referrer = Column(Text, nullable=True)

    # Visitor (privacy-safe: IP is hashed, not stored raw)
    ip_hash = Column(String(64), nullable=True)
    country = Column(String(2), nullable=True)
    region = Column(String(128), nullable=True)
    city = Column(String(128), nullable=True)
    asn = Column(String(64), nullable=True)
    timezone = Column(String(64), nullable=True)

    # Device
    browser = Column(String(64), nullable=True)
    browser_version = Column(String(32), nullable=True)
    os = Column(String(64), nullable=True)
    device_type = Column(String(32), nullable=True)  # desktop/mobile/tablet
    screen_width = Column(Integer, nullable=True)
    screen_height = Column(Integer, nullable=True)
    language = Column(String(16), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Behavior
    duration_seconds = Column(Float, nullable=True)
    scroll_depth = Column(Integer, nullable=True)  # 0-100 percent

    # UTM campaign attribution
    utm_source = Column(String(256), nullable=True)
    utm_medium = Column(String(256), nullable=True)
    utm_campaign = Column(String(256), nullable=True)
    utm_content = Column(String(256), nullable=True)
    utm_term = Column(String(256), nullable=True)

    # Entry context
    anchor = Column(String(512), nullable=True)   # URL fragment (#section)
    search_query = Column(String(512), nullable=True)  # query from referrer URL

    # Flags
    is_bot = Column(Boolean, default=False)
    is_unique = Column(Boolean, default=False)
    is_404 = Column(Boolean, default=False)

    # Performance (optional, from JS)
    lcp = Column(Float, nullable=True)
    fcp = Column(Float, nullable=True)
    ttfb = Column(Float, nullable=True)

    # Extra data bucket
    meta = Column(JSON, nullable=True)
