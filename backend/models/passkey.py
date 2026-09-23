from sqlalchemy import Column, String, DateTime, Integer, LargeBinary, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database import Base


class Passkey(Base):
    """A WebAuthn credential registered by a user (m007). Optional sign-in alongside
    the password; the public key is all that is stored."""

    __tablename__ = "passkeys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    credential_id = Column(LargeBinary, nullable=False, unique=True)
    public_key = Column(LargeBinary, nullable=False)
    sign_count = Column(Integer, nullable=False, default=0)
    transports = Column(Text, nullable=True)       # JSON list
    name = Column(String(120), nullable=True)      # "MacBook Touch ID"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
