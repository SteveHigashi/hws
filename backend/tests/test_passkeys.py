"""Passkey sign-in through the real routes with a software authenticator (ES256).

Remove the sign-count check or the origin check in routers/passkeys.py and a test fails.
"""
import asyncio
import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/pk.db"

import cbor2  # noqa: E402
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from webauthn.helpers import bytes_to_base64url  # noqa: E402

import database  # noqa: E402
import main  # noqa: E402
from database import Base, get_db  # noqa: E402
from models.user import User, UserRole  # noqa: E402
from routers.auth import _hash_pw, create_access_token  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

ORIGIN = "http://localhost"


class SoftAuthenticator:
    def __init__(self):
        self.priv = ec.generate_private_key(ec.SECP256R1())
        pub = self.priv.public_key().public_numbers()
        self.cred_id = os.urandom(16)
        self.cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: pub.x.to_bytes(32, "big"), -3: pub.y.to_bytes(32, "big")})

    def auth_data(self, rp_id, flags, count, with_cred):
        d = hashlib.sha256(rp_id.encode()).digest() + bytes([flags]) + struct.pack(">I", count)
        if with_cred:
            d += b"\x00" * 16 + struct.pack(">H", len(self.cred_id)) + self.cred_id + self.cose
        return d

    @staticmethod
    def client_data(kind, challenge, origin):
        return json.dumps({"type": kind, "challenge": challenge, "origin": origin, "crossOrigin": False}).encode()

    def register(self, opts, origin=ORIGIN):
        cd = self.client_data("webauthn.create", opts["challenge"], origin)
        att = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": self.auth_data(opts["rp"]["id"], 0x45, 0, True)})
        return {"id": bytes_to_base64url(self.cred_id), "rawId": bytes_to_base64url(self.cred_id), "type": "public-key",
                "response": {"clientDataJSON": bytes_to_base64url(cd), "attestationObject": bytes_to_base64url(att), "transports": ["internal"]}}

    def assert_(self, opts, count, origin=ORIGIN):
        cd = self.client_data("webauthn.get", opts["challenge"], origin)
        ad = self.auth_data(opts["rpId"], 0x05, count, False)
        sig = self.priv.sign(ad + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
        return {"id": bytes_to_base64url(self.cred_id), "rawId": bytes_to_base64url(self.cred_id), "type": "public-key",
                "response": {"clientDataJSON": bytes_to_base64url(cd), "authenticatorData": bytes_to_base64url(ad), "signature": bytes_to_base64url(sig)}}


class PasskeyTests(unittest.TestCase):
    """Bound to its own database.

    Setting DATABASE_URL at import time is not enough: whichever test module imports
    `database` first builds the engine, and under the full suite that is somebody else's
    module reading backend/.env — which points at the developer's own higashi.db. This
    class therefore builds its own engine and overrides get_db, so the result does not
    depend on collection order and no test ever writes into a real database.
    """

    @classmethod
    def setUpClass(cls):
        cls._engine = create_async_engine(os.environ["DATABASE_URL"], connect_args={"timeout": 30})
        cls._sessions = async_sessionmaker(cls._engine, expire_on_commit=False)

        async def seed():
            async with cls._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with cls._sessions() as db:
                db.add(User(id=uuid.uuid4(), email="pk@example.test", password_hash=_hash_pw("password-ten"), role=UserRole.admin))
                await db.commit()
        asyncio.run(seed())

        async def _override():
            async with cls._sessions() as db:
                yield db
        main.app.dependency_overrides[get_db] = _override
        cls._saved_sessions = database.AsyncSessionLocal
        database.AsyncSessionLocal = cls._sessions

        cls.client = TestClient(main.app, base_url=ORIGIN)
        cls.auth = {"Authorization": "Bearer " + create_access_token({"sub": "pk@example.test", "role": "admin"}), "Origin": ORIGIN}
        cls.key = SoftAuthenticator()
        r = cls.client.post("/api/auth/passkeys/register/options", headers=cls.auth)
        assert r.status_code == 200, r.text
        r = cls.client.post("/api/auth/passkeys/register/verify", headers=cls.auth,
                            json={"state": r.json()["state"], "credential": cls.key.register(r.json()["options"]), "name": "test key"})
        assert r.status_code == 200, r.text

    @classmethod
    def tearDownClass(cls):
        main.app.dependency_overrides.pop(get_db, None)
        database.AsyncSessionLocal = cls._saved_sessions
        asyncio.run(cls._engine.dispose())

    def _sign_in(self, count, origin=ORIGIN, claim_origin=ORIGIN):
        r = self.client.post("/api/auth/passkeys/login/options", headers={"Origin": origin}, json={"email": "pk@example.test"})
        state, opts = r.json()["state"], r.json()["options"]
        return self.client.post("/api/auth/passkeys/login/verify", headers={"Origin": claim_origin},
                                json={"state": state, "credential": self.key.assert_(opts, count, origin)})

    def test_1_registered_key_is_listed(self):
        names = [k["name"] for k in self.client.get("/api/auth/passkeys", headers=self.auth).json()]
        self.assertEqual(names, ["test key"])

    def test_2_sign_in_returns_a_token(self):
        r = self._sign_in(1)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["access_token"])

    def test_3_a_replayed_sign_count_is_refused(self):
        self.assertEqual(self._sign_in(1).status_code, 401)  # count did not move: cloned authenticator
        self.assertEqual(self._sign_in(7).status_code, 200)

    def test_4_a_signature_for_another_origin_is_refused(self):
        self.assertEqual(self._sign_in(20, origin="http://evil.test", claim_origin=ORIGIN).status_code, 401)

    def test_5_a_challenge_cannot_be_reused(self):
        r = self.client.post("/api/auth/passkeys/login/options", headers={"Origin": ORIGIN}, json={"email": "pk@example.test"})
        state, opts = r.json()["state"], r.json()["options"]
        cred = self.key.assert_(opts, 30)
        self.assertEqual(self.client.post("/api/auth/passkeys/login/verify", headers={"Origin": ORIGIN}, json={"state": state, "credential": cred}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/passkeys/login/verify", headers={"Origin": ORIGIN}, json={"state": state, "credential": cred}).status_code, 400)

    def test_6_unknown_credential_is_401(self):
        other = SoftAuthenticator()
        r = self.client.post("/api/auth/passkeys/login/options", headers={"Origin": ORIGIN}, json={})
        state, opts = r.json()["state"], r.json()["options"]
        self.assertEqual(self.client.post("/api/auth/passkeys/login/verify", headers={"Origin": ORIGIN},
                                          json={"state": state, "credential": other.assert_(opts, 1)}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
