"""Password reset without assuming the install can send mail.

The operator runs `manage_users.py reset-link <email>` on the server; it prints a link
that works once, for 30 minutes. Only the token's SHA-256 is stored. When an install
has SMTP configured (later), the same token can be mailed instead — the API and the
page do not change.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.password_reset import PasswordReset
from models.user import User

RESET_TTL = timedelta(minutes=30)


def reset_mode() -> str:
    return "server"  # "mail" once SMTP settings exist


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_reset_token(db: AsyncSession, email: str) -> str | None:
    """Create a one-time token for the user; returns the raw token (shown once) or None."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        return None
    raw = secrets.token_urlsafe(32)
    db.add(PasswordReset(user_id=user.id, token_hash=hash_reset_token(raw),
                         expires_at=datetime.now(timezone.utc) + RESET_TTL))
    await db.commit()
    return raw


async def consume_reset_token(db: AsyncSession, raw: str) -> User | None:
    """Mark the token used and return its user, or None if unknown, used or expired."""
    row = (await db.execute(
        select(PasswordReset).where(PasswordReset.token_hash == hash_reset_token(raw or ""))
    )).scalar_one_or_none()
    if row is None or row.used_at is not None:
        return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        return None
    user = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
    if user is None:
        return None
    row.used_at = datetime.now(timezone.utc)
    return user
