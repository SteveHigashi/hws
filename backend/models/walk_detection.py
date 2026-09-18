import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database import Base


class WalkDetectionRun(Base):
    """One privacy-safe, after-the-fact analysis window."""

    __tablename__ = "walk_detection_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    verdict = Column(String(32), nullable=False, index=True)
    headline = Column(String(256), nullable=False)
    score = Column(Integer, nullable=False, default=0)
    triggers = Column(JSON, nullable=False, default=list)
    signals = Column(JSON, nullable=False, default=list)

    records_taken = Column(Integer, nullable=False, default=0)
    total_content_requests = Column(Integer, nullable=False, default=0)
    distinct_identities = Column(Integer, nullable=False, default=0)
    shape_oneshot_identities = Column(Integer, nullable=False, default=0)
    shape_share = Column(Float, nullable=False, default=0)
    order_pairs = Column(Integer, nullable=False, default=0)
    order_ratio = Column(Float, nullable=False, default=0)
    content_responses = Column(Integer, nullable=False, default=0)
    asset_responses = Column(Integer, nullable=False, default=0)
    assetless_identity_share = Column(Float, nullable=False, default=0)
    referer_absence_ratio = Column(Float, nullable=False, default=0)
    shared_queue_pairs = Column(Integer, nullable=False, default=0)
    shared_queue_ratio = Column(Float, nullable=False, default=0)
    median_requests_per_address_day = Column(Float, nullable=False, default=0)
    p95_requests_per_address_day = Column(Float, nullable=False, default=0)
    singleton_address_share = Column(Float, nullable=False, default=0)
    rate_blind_spot = Column(Boolean, nullable=False, default=False)
    forged_claims = Column(Integer, nullable=False, default=0)
    verified_claims = Column(Integer, nullable=False, default=0)
    unverified_claims = Column(Integer, nullable=False, default=0)
    engagement_absence_ratio = Column(Float, nullable=True)
