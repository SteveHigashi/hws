from sqlalchemy import Column, String, DateTime, Boolean, Text, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class GeoProbeQuery(Base):
    __tablename__ = "geo_probe_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    brand_name = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GeoProbeResult(Base):
    __tablename__ = "geo_probe_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    probe_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    model = Column(String(64), nullable=False)
    ran_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    mentioned = Column(Boolean, default=False)
    mention_excerpt = Column(Text, nullable=True)
    full_response = Column(Text, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
