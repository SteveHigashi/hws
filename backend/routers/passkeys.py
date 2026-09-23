"""Passkey (WebAuthn) sign-in, optional alongside email + password.

The relying party is whatever host the dashboard is served from: RP id = the request's
hostname, expected origin = the browser's Origin header. That is what lets one build
run on any domain a self-hoster picks. Challenges live in memory for five minutes;
a restart simply asks the browser to start again.
"""
from __future__ import annotations

import json
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from database import get_db
from models.passkey import Passkey
from models.user import User
from routers.auth import Token, create_access_token, get_current_user

router = APIRouter()

_CHALLENGE_TTL = 300.0
_challenges: dict[str, tuple[float, bytes, str, Optional[str]]] = {}   # state -> (expires, challenge, kind, user_id)


def _rp(request: Request) -> tuple[str, str, str]:
    """(rp_id, rp_name, expected_origin) from the request the browser made."""
    host = request.url.hostname or "localhost"
    origin = request.headers.get("origin") or f"{request.url.scheme}://{request.headers.get('host', host)}"
    return host, "Higashi Analytics", origin


def _remember(challenge: bytes, kind: str, user_id: Optional[str]) -> str:
    now = time.monotonic()
    for key in [k for k, v in _challenges.items() if v[0] < now]:
        _challenges.pop(key, None)
    state = secrets.token_urlsafe(24)
    _challenges[state] = (now + _CHALLENGE_TTL, challenge, kind, user_id)
    return state


def _recall(state: str, kind: str) -> tuple[bytes, Optional[str]]:
    item = _challenges.pop(state or "", None)
    if item is None or item[0] < time.monotonic() or item[2] != kind:
        raise HTTPException(status_code=400, detail="This sign-in attempt expired. Start again.")
    return item[1], item[3]


class StateAndCredential(BaseModel):
    state: str
    credential: dict
    name: Optional[str] = None


class LoginOptionsRequest(BaseModel):
    email: Optional[str] = None


# ---- registration (signed-in user adds a passkey) --------------------------------

@router.post("/register/options")
async def register_options(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rp_id, rp_name, _origin = _rp(request)
    existing = (await db.execute(select(Passkey).where(Passkey.user_id == user.id))).scalars().all()
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=user.id.bytes,
        user_name=user.email,
        user_display_name=user.email,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=p.credential_id) for p in existing],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    state = _remember(options.challenge, "register", str(user.id))
    return {"state": state, "options": json.loads(options_to_json(options))}


@router.post("/register/verify")
async def register_verify(body: StateAndCredential, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rp_id, _name, origin = _rp(request)
    challenge, user_id = _recall(body.state, "register")
    if user_id != str(user.id):
        raise HTTPException(status_code=400, detail="This registration belongs to another sign-in.")
    try:
        verified = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"The passkey could not be verified: {exc}")
    transports = body.credential.get("response", {}).get("transports")
    db.add(Passkey(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=json.dumps(transports) if transports else None,
        name=(body.name or "Passkey")[:120],
    ))
    await db.commit()
    return {"ok": True}


# ---- sign-in -------------------------------------------------------------------

@router.post("/login/options")
async def login_options(body: LoginOptionsRequest, request: Request, db: AsyncSession = Depends(get_db)):
    rp_id, _name, _origin = _rp(request)
    allow: list[PublicKeyCredentialDescriptor] = []
    user_id = None
    if body.email:
        user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
        if user is not None:
            user_id = str(user.id)
            keys = (await db.execute(select(Passkey).where(Passkey.user_id == user.id))).scalars().all()
            allow = [PublicKeyCredentialDescriptor(id=p.credential_id) for p in keys]
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    state = _remember(options.challenge, "login", user_id)
    return {"state": state, "options": json.loads(options_to_json(options))}


@router.post("/login/verify", response_model=Token)
async def login_verify(body: StateAndCredential, request: Request, db: AsyncSession = Depends(get_db)):
    rp_id, _name, origin = _rp(request)
    challenge, _user_id = _recall(body.state, "login")
    raw_id = body.credential.get("rawId") or body.credential.get("id") or ""
    try:
        credential_id = base64url_to_bytes(raw_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed credential")
    passkey = (await db.execute(select(Passkey).where(Passkey.credential_id == credential_id))).scalar_one_or_none()
    if passkey is None:
        raise HTTPException(status_code=401, detail="Unknown passkey")
    user = (await db.execute(select(User).where(User.id == passkey.user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown passkey")
    try:
        verified = verify_authentication_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"The passkey could not be verified: {exc}")
    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now(timezone.utc)
    user.last_login = datetime.utcnow()
    await db.commit()
    token = create_access_token({"sub": user.email, "role": user.role})
    return Token(access_token=token, token_type="bearer", role=user.role)


# ---- management ----------------------------------------------------------------

@router.get("")
async def list_passkeys(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    keys = (await db.execute(select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.created_at))).scalars().all()
    return [
        {"id": str(p.id), "name": p.name, "created_at": p.created_at.isoformat() if p.created_at else None,
         "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
         "credential_id": bytes_to_base64url(p.credential_id)[:12] + "…"}
        for p in keys
    ]


@router.delete("/{passkey_id}")
async def delete_passkey(passkey_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    p = (await db.execute(select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == user.id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="No such passkey")
    await db.delete(p)
    await db.commit()
    return {"ok": True}
