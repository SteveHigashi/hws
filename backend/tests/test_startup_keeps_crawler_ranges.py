"""Application startup must not blank out crawler verification.

main.py calls load_local_live_ranges() at startup. It used to swap the whole
prefix index for backend/data/crawler_ranges.live.json on nothing more than that
file existing, and a one-family test fixture, {"fam": ["1.2.3.0/24"]}, shipped in
every release tarball. So every install booted with twelve real crawler families
replaced by one fake one, and every crawler read unverified no matter where it
came from.

It went unnoticed because the CLI log importer runs in its own process and never
executes main.py, so imported rows carried correct verdicts and the dashboard
looked right. Only traffic classified inside the running application, which is
the live tracker beacon, was affected.

These tests drive the startup hook itself rather than importing services.bot and
checking it in isolation, which is what earlier testing did and is why it passed
while the application was broken.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services import bot as bot_module  # noqa: E402
from services import live_client  # noqa: E402
from services.bot import classify_bot, reload_crawler_ranges  # noqa: E402

GOOGLE_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
GOOGLE_IP = "66.249.70.1"


class StartupRangeLoadingTests(unittest.TestCase):
    def setUp(self):
        self._original = live_client._LIVE_RANGES_FILE
        self.addCleanup(self._restore)
        reload_crawler_ranges()                      # the bundled list

    def _restore(self):
        live_client._LIVE_RANGES_FILE = self._original
        reload_crawler_ranges()

    def _point_at(self, payload):
        d = Path(tempfile.mkdtemp())
        p = d / "crawler_ranges.live.json"
        p.write_text(json.dumps(payload))
        live_client._LIVE_RANGES_FILE = p
        return p

    def _families(self):
        return set(bot_module._PREFIX_INDEX._families)

    # --- the regression -----------------------------------------------------

    def test_a_stub_file_does_not_replace_the_real_ranges(self):
        before = self._families()
        self.assertGreater(len(before), 1, "fixture problem: bundled ranges not loaded")
        self._point_at({"fam": ["1.2.3.0/24"]})       # the file that used to ship

        self.assertFalse(
            live_client.load_local_live_ranges(),
            "startup accepted a file carrying no family the verifier knows",
        )
        self.assertEqual(
            self._families(), before,
            "startup replaced the real crawler ranges with a stub, which disables "
            "verification for every crawler on the install",
        )

    def test_verification_still_works_after_the_startup_hook(self):
        self._point_at({"fam": ["1.2.3.0/24"]})
        live_client.load_local_live_ranges()
        self.assertEqual(
            classify_bot(GOOGLE_UA, ip_address=GOOGLE_IP)["verification_state"],
            "verified",
            "a real Googlebot address stopped verifying after application startup",
        )

    # --- other ways the file can be useless ---------------------------------

    def test_malformed_json_is_refused(self):
        d = Path(tempfile.mkdtemp())
        p = d / "crawler_ranges.live.json"
        p.write_text("{not json")
        live_client._LIVE_RANGES_FILE = p
        before = self._families()
        self.assertFalse(live_client.load_local_live_ranges())
        self.assertEqual(self._families(), before)

    def test_an_empty_or_valueless_file_is_refused(self):
        for payload in ({}, {"googlebot": []}, {"googlebot": "not-a-list"}, []):
            with self.subTest(payload=payload):
                reload_crawler_ranges()
                before = self._families()
                self._point_at(payload)
                self.assertFalse(live_client.load_local_live_ranges())
                self.assertEqual(self._families(), before)

    def test_a_missing_file_is_fine(self):
        live_client._LIVE_RANGES_FILE = Path(tempfile.mkdtemp()) / "absent.json"
        before = self._families()
        self.assertFalse(live_client.load_local_live_ranges())
        self.assertEqual(self._families(), before)

    # --- a genuine Live file is still honoured -------------------------------

    def test_a_real_live_file_is_accepted(self):
        self._point_at({"googlebot": ["66.249.70.0/24"], "gptbot": ["132.196.86.0/24"]})
        self.assertTrue(
            live_client.load_local_live_ranges(),
            "a Live file naming families the verifier knows must still be loaded",
        )
        self.assertEqual(
            classify_bot(GOOGLE_UA, ip_address=GOOGLE_IP)["verification_state"], "verified")

    def test_usability_is_judged_against_the_verifier_rules(self):
        # Not a hardcoded list: a family added to bot.py is accepted here with no
        # second edit, and one the verifier has no rule for is not.
        known = {g for r in bot_module._NETWORK_RULES.values() for g in r["groups"]}
        self.assertIn("gptbot", known)
        p = self._point_at({"gptbot": ["132.196.86.0/24"]})
        self.assertTrue(live_client.live_ranges_are_usable(p))
        p = self._point_at({"not-a-real-family": ["1.2.3.0/24"]})
        self.assertFalse(live_client.live_ranges_are_usable(p))


class ReleaseHygieneTests(unittest.TestCase):
    def test_the_live_ranges_file_is_not_in_the_repository(self):
        # It is per-install state, like a database or a settings file.
        self.assertFalse(
            (BACKEND / "data" / "crawler_ranges.live.json").exists(),
            "crawler_ranges.live.json is back in the repository and will ship again",
        )

    def test_the_release_script_excludes_it(self):
        script = (BACKEND.parent / "release" / "release.sh").read_text()
        self.assertIn("--exclude='crawler_ranges.live.json'", script)


if __name__ == "__main__":
    unittest.main()
