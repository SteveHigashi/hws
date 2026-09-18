from sqlalchemy import Column, String, DateTime, Integer, Boolean, Float, Text, SmallInteger, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class BehaviorEvent(Base):
    """
    High-frequency behavioral signals captured by the enhanced tracker.
    Separate table from events — higher volume, different retention rules.
    Default retention: 30 days raw (configurable), rolled up into aggregates.
    """
    __tablename__ = "behavior_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    page_url = Column(Text, nullable=False)

    # Event type: click | select | scroll_pause | tab_blur | tab_focus |
    #             form_field | media | error | copy | print | external_click
    event_type = Column(String(32), nullable=False, index=True)

    # Click / interaction position
    x = Column(Integer, nullable=True)        # viewport x px
    y = Column(Integer, nullable=True)        # viewport y px
    x_pct = Column(SmallInteger, nullable=True)   # % of page width
    y_pct = Column(SmallInteger, nullable=True)   # % of page height

    # Element context
    element_tag = Column(String(32), nullable=True)     # a, button, input, etc.
    element_id = Column(String(256), nullable=True)
    element_class = Column(String(512), nullable=True)
    element_text = Column(String(256), nullable=True)   # truncated visible text
    href = Column(Text, nullable=True)                  # for links / external clicks

    # Text selection
    selected_text = Column(Text, nullable=True)         # what they highlighted (max 1KB)

    # Timing / duration signals
    duration_ms = Column(Integer, nullable=True)        # time hovering, pausing, etc.
    idle_ms = Column(Integer, nullable=True)            # cursor idle before this event

    # Scroll context
    scroll_y = Column(Integer, nullable=True)           # scroll position at event
    scroll_pct = Column(SmallInteger, nullable=True)    # 0-100

    # Form
    field_name = Column(String(256), nullable=True)
    field_type = Column(String(64), nullable=True)      # text, email, select, etc.
    field_action = Column(String(16), nullable=True)    # focus | blur | submit | abandon

    # Media
    media_src = Column(Text, nullable=True)
    media_action = Column(String(16), nullable=True)    # play | pause | ended | seek
    media_position = Column(Float, nullable=True)       # seconds into media

    # Error
    error_message = Column(Text, nullable=True)
    error_source = Column(Text, nullable=True)
    error_line = Column(Integer, nullable=True)

    # Rage / dead click detection (computed server-side)
    is_rage_click = Column(Boolean, default=False)
    is_dead_click = Column(Boolean, default=False)

    # Flexible overflow
    meta = Column(JSON, nullable=True)
