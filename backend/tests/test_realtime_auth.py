"""The realtime stream authenticates by header, and a token in the URL buys nothing.

On 2026-09-23 the dashboard opened this endpoint as `?token=<session jwt>`, because
EventSource cannot set headers. That put a live admin token — good for another 26 days —
into journald and the nginx access log, and it never worked either: the endpoint only
ever read the Authorization header, so every connection was a 401 and the Real-time feed
had quietly been dead.

Make the endpoint accept `?token=` and the first test fails.
"""
import asyncio
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp}/realtime.db"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import database  # noqa: E402
import main  # noqa: E402
from database import Base, get_db  # noqa: E402
from models.site import Site  # noqa: E402
from models.user import User, UserRole  # noqa: E402
from routers.auth import _hash_pw, create_access_token  # noqa: E402


class RealtimeAuthTests(unittest.TestCase):
    """Bound to its own database, so the result does not depend on collection order."""

    @classmethod
    def setUpClass(cls):
        cls._engine = create_async_engine(os.environ["DATABASE_URL"], connect_args={"timeout": 30})
        cls._sessions = async_sessionmaker(cls._engine, expire_on_commit=False)

        async def seed():
            async with cls._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with cls._sessions() as db:
                db.add(User(id=uuid.uuid4(), email="rt@example.test",
                            password_hash=_hash_pw("password-ten"), role=UserRole.admin))
                db.add(Site(id=uuid.uuid4(), domain="rt.example.test", name="rt"))
                await db.commit()
        asyncio.run(seed())

        async def _override():
            async with cls._sessions() as db:
                yield db
        main.app.dependency_overrides[get_db] = _override
        cls._saved = database.AsyncSessionLocal
        database.AsyncSessionLocal = cls._sessions

        cls.client = TestClient(main.app)
        cls.token = create_access_token({"sub": "rt@example.test", "role": "admin"})

    @classmethod
    def tearDownClass(cls):
        main.app.dependency_overrides.pop(get_db, None)
        database.AsyncSessionLocal = cls._saved
        asyncio.run(cls._engine.dispose())

    def test_a_token_in_the_query_string_is_not_accepted(self):
        """The whole point: putting the credential in the URL must not authenticate."""
        response = self.client.get(f"/api/intelligence/realtime?token={self.token}")
        self.assertEqual(response.status_code, 401, response.text)

    def test_no_credential_at_all_is_401(self):
        self.assertEqual(self.client.get("/api/intelligence/realtime").status_code, 401)

    def test_a_bad_header_is_401(self):
        response = self.client.get("/api/intelligence/realtime",
                                   headers={"Authorization": "Bearer not-a-token"})
        self.assertEqual(response.status_code, 401)

    def test_the_route_is_guarded_by_the_normal_header_dependency(self):
        """Not consumed as a stream on purpose: the endpoint polls forever, and reading
        it from TestClient hangs the suite. The security claim is what is asserted here —
        that the ordinary header dependency guards it and no token parameter exists."""
        route = next(r for r in main.app.routes if getattr(r, "path", "") == "/api/intelligence/realtime")
        guards = {d.call.__name__ for d in route.dependant.dependencies if getattr(d, "call", None)}
        self.assertIn("get_current_user", guards)
        params = {p.name for p in route.dependant.query_params}
        self.assertNotIn("token", params, "a token query parameter is exactly what we removed")
        self.assertIn("site_id", params)

    def test_the_stream_does_not_hold_the_request_session(self):
        """A `while True` poll on the request's session leaks a pooled connection per
        open tab. Each pass must take its own short-lived session instead."""
        source = (BACKEND / "routers" / "intelligence.py").read_text()
        stream = source[source.index("async def realtime_stream"):source.index("class AskRequest")]
        self.assertIn("async with AsyncSessionLocal() as poll_db", stream)
        self.assertNotIn("await db.execute", stream.split("async def event_stream")[1])


if __name__ == "__main__":
    unittest.main()
