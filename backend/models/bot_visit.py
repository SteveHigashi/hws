from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class BotVisit(Base):
    __tablename__ = "bot_visits"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id      = Column(UUID(as_uuid=True), nullable=False, index=True)
    timestamp    = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    page_path    = Column(Text, nullable=True, index=True)
    bot_name     = Column(String(64), nullable=False, index=True)
    bot_category = Column(String(32), nullable=False, index=True)
    country      = Column(String(2), nullable=True)
    user_agent   = Column(Text, nullable=True)
    # Persist the import-time verdict, never the raw address used to reach it.
    verification_state  = Column(String(16), nullable=False, default="unverified", index=True)
    verification_method = Column(String(32), nullable=True)
    ip_hash       = Column(String(64), nullable=True, index=True)
    http_status   = Column(Integer, nullable=True)
    response_bytes = Column(Integer, nullable=True)
    referrer      = Column(Text, nullable=True)
