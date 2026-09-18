"""Secrets stay server-side: saved pull logins, AI key previews, installer layout."""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import config  # noqa: E402
from database import Base  # noqa: E402
from models.pull_profile import PullProfile  # noqa: E402
from routers import admin as admin_router  # noqa: E402
from routers import import_logs  # noqa: E402
from services import secret_box  # noqa: E402

PASSWORD = "hunter2-correct-horse-battery"
PRIVATE_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAAtestkeymaterial\n-----END OPENSSH PRIVATE KEY-----"


def run(coro):
    return asyncio.run(coro)


class SecretBoxTests(unittest.TestCase):
    def test_round_trip_and_no_plaintext(self):
        token = secret_box.encrypt(PASSWORD)
        self.assertNotIn(PASSWORD, token)
        self.assertEqual(secret_box.decrypt(token), PASSWORD)

    def test_other_secret_key_cannot_decrypt(self):
        token = secret_box.encrypt(PASSWORD)
        other = config.Settings(secret_key="a-different-install-secret")
        with patch.object(secret_box, "get_settings", return_value=other):
            with self.assertRaises(Exception):
                secret_box.decrypt(token)


class PullProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        engine = create_async_engine(f"sqlite+aiosqlite:///{self.tmp.name}/t.db")

        async def init():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        run(init())
        self.engine = engine
        self.patch = patch.object(import_logs, "AsyncSessionLocal", async_sessionmaker(engine, expire_on_commit=False))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        run(self.engine.dispose())
        self.tmp.cleanup()

    def _save(self, **kw):
        body = dict(label="site", host="logs.example.com", port=22, username="deploy",
                    auth_mode="password", password=PASSWORD, domain="example.com", log_paths=["/var/log/a.log"])
        body.update(kw)
        return run(import_logs.save_profile(import_logs.PullProfileRequest(**body), _=None))

    def _row(self, pid):
        async def get():
            async with import_logs.AsyncSessionLocal() as db:
                return await db.get(PullProfile, pid)
        return run(get())

    def test_secret_never_returned_and_encrypted_at_rest(self):
        saved = self._save()
        listed = run(import_logs.list_profiles(_=None))
        for out in (saved, *listed):
            text = repr(out)
            self.assertNotIn(PASSWORD, text)
            self.assertNotIn("secret_enc", text)
            self.assertNotIn("password", out)
        self.assertTrue(listed[0]["has_secret"])
        self.assertNotIn(PASSWORD, self._row(saved["id"]).secret_enc)

    def test_saved_secret_only_goes_to_its_own_host(self):
        saved = self._save()
        body = import_logs.SSHCredentials(profile_id=saved["id"], host="attacker.example.net", username="root")
        host, port, username, password, key = run(import_logs._resolve_credentials(body))
        self.assertEqual((host, username, password), ("logs.example.com", "deploy", PASSWORD))

    def test_changing_target_without_secret_drops_stored_secret(self):
        saved = self._save()
        self._save(host="other.example.net", password="")
        self.assertIsNone(self._row(saved["id"]).secret_enc)

    def test_resave_same_target_keeps_secret(self):
        saved = self._save()
        self._save(password="", log_paths=["/var/log/b.log"])
        self.assertEqual(secret_box.decrypt(self._row(saved["id"]).secret_enc), PASSWORD)

    def test_private_key_profile(self):
        saved = self._save(auth_mode="key", password=None, private_key=PRIVATE_KEY)
        self.assertNotIn("AAAAtestkeymaterial", repr(run(import_logs.list_profiles(_=None))))
        _, _, _, password, key = run(import_logs._resolve_credentials(import_logs.SSHCredentials(profile_id=saved["id"])))
        self.assertEqual((password, key), (None, PRIVATE_KEY))

    def test_env_password_not_sent_to_other_hosts(self):
        fake = config.Settings(sftp_host="mine.example.com", sftp_password=PASSWORD, secret_key="x" * 64)
        with patch.object(import_logs, "settings", fake):
            other = run(import_logs._resolve_credentials(import_logs.SSHCredentials(host="attacker.example.net", username="u")))
            mine = run(import_logs._resolve_credentials(import_logs.SSHCredentials(username="u")))
        self.assertIsNone(other[3])
        self.assertEqual(mine[3], PASSWORD)


class AIKeyExposureTests(unittest.TestCase):
    def test_preview_shows_only_last_four(self):
        key = "sk-ant-api03-" + "Z" * 80 + "wxyz"
        self.assertEqual(admin_router._key_tail(key), "…wxyz")

    def test_validation_error_does_not_echo_provider_message(self):
        key = "sk-ant-api03-SECRETMATERIAL1234567890"

        class Boom(Exception):
            status_code = 401

        class FakeClient:
            def __init__(self, api_key):
                self.models = self

            async def list(self):
                raise Boom(f"invalid x-api-key {key}")

        import anthropic
        from fastapi import HTTPException
        with patch.object(anthropic, "AsyncAnthropic", FakeClient):
            with self.assertRaises(HTTPException) as ctx:
                run(admin_router.save_ai_key(admin_router.AIKeyRequest(anthropic_api_key=key), _=None))
        self.assertNotIn("SECRETMATERIAL", ctx.exception.detail)

    def test_env_writes_are_owner_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "settings.env")
            Path(p).write_text("")
            os.chmod(p, 0o644)
            admin_router.dotenv_set_key(p, "ANTHROPIC_API_KEY", "k")
            self.assertEqual(os.stat(p).st_mode & 0o777, 0o600)


class SecretKeyDefaultTests(unittest.TestCase):
    def test_default_secret_key_is_replaced_and_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            env_path = os.path.join(d, "settings.env")
            Path(env_path).write_text("")
            env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
            env["HIGASHI_ENV_PATH"] = env_path
            with patch.dict(os.environ, env, clear=True), \
                 patch.object(config.Settings, "model_config", {**config.Settings.model_config, "env_file": None}):
                config.get_settings.cache_clear()
                try:
                    key = config.get_settings().secret_key
                finally:
                    config.get_settings.cache_clear()
            self.assertNotEqual(key, config.DEFAULT_SECRET_KEY)
            self.assertIn(f"SECRET_KEY='{key}'", Path(env_path).read_text())


class NoSecretsInBrowserOrWebRootTests(unittest.TestCase):
    def test_import_page_does_not_store_logins_in_browser(self):
        src = (ROOT / "frontend/src/pages/Import.jsx").read_text()
        self.assertNotIn("localStorage.setItem", src)
        self.assertNotIn("btoa(", src)

    def test_installer_keeps_settings_and_db_out_of_web_root(self):
        src = (ROOT / "softaculous/install.php").read_text()
        self.assertNotIn('"$install_dir/settings.env";\nif (!file_exists', src)
        self.assertIn('$settings_file = "$data_dir/settings.env"', src)
        self.assertIn('$db_path       = "$data_dir/higashi.db"', src)
        self.assertRegex(src, r"FilesMatch \"[^\"]*env\|db\|sqlite")


if __name__ == "__main__":
    unittest.main()
