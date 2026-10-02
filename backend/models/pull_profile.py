import uuid
from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.sql import func
from database import Base


class PullProfile(Base):
    """A saved SSH log-pull target. The secret is stored encrypted and never returned."""
    __tablename__ = "pull_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    label = Column(String(120), nullable=False, unique=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=22)
    username = Column(String(120), nullable=False)
    auth_mode = Column(String(16), nullable=False, default="password")  # "password" | "key"
    secret_enc = Column(Text, nullable=True)
    domain = Column(String(255), nullable=True)
    log_paths = Column(Text, nullable=True)  # JSON list
    schedule = Column(String(16), nullable=False, default="off", server_default="off")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
