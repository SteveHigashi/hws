"""The admin UI, the secret-key persistence and the settings loader must all
use ONE file. Until 2026-09-18 the loader read ./.env while the writers used
HIGASHI_ENV_PATH, so a key saved through the UI on any install that set the
variable was reported saved and never read. Run with throwaway files only.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class SettingsFileAgreementTests(unittest.TestCase):
    def _fresh(self):
        # routers.admin imports the database engine; keep it off Postgres here
        os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
        import config
        import routers.admin as admin
        config.get_settings.cache_clear()
        return config, admin

    def test_writers_and_loader_resolve_the_same_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "settings.env")
            with patch.dict(os.environ, {"HIGASHI_ENV_PATH": p}):
                config, admin = self._fresh()
                self.assertEqual(config.env_file_path(), p)
                self.assertEqual(admin._env_path(), p)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HIGASHI_ENV_PATH", None)
            config, admin = self._fresh()
            expected = str(Path(config.__file__).resolve().parent / ".env")
            self.assertEqual(os.path.abspath(config.env_file_path()), expected)
            self.assertEqual(os.path.abspath(admin._env_path()), expected)

    def test_a_key_saved_by_the_admin_path_is_visible_after_reload(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "settings.env")
            Path(p).write_text("SECRET_KEY=test-only-not-a-real-key\n")
            env = {"HIGASHI_ENV_PATH": p}
            # the loader must read the FILE, so the value must not sit in os.environ
            with patch.dict(os.environ, env):
                os.environ.pop("LIVE_KEY", None)
                config, admin = self._fresh()
                self.assertEqual(config.get_settings().live_key, "")
                admin.dotenv_set_key(admin._env_path(), "LIVE_KEY", "fake-live-key-for-test")
                config.get_settings.cache_clear()
                self.assertEqual(config.get_settings().live_key, "fake-live-key-for-test")
                self.assertEqual(oct(os.stat(p).st_mode & 0o777), "0o600")
                self.assertNotIn("LIVE_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
