"""Stale published ranges must not produce a forgery accusation.

`_verification_for` calls an address outside a vendor's published prefixes
`forged`, which the dashboard renders as "Crawler identity forgery detected ...
Treat these as impersonation". That is only fair while the prefixes are current.
Operators add egress regularly, and a self-hosted install whose refresh has
stopped would otherwise start accusing legitimate Googlebot traffic of
impersonation purely because its copy of the ranges had aged.

Fresh data behaves exactly as before. Stale data decides nothing in either
direction. Staleness cuts both ways: an operator that adds egress makes an old
file accuse legitimate traffic, and an operator that releases a prefix makes an
old file authenticate whoever is allocated it next, which is the quieter failure
because a forged crawler collects a verified badge rather than a red banner.

FCrDNS is deliberately not gated on file age. It is a live lookup against the
operator's own DNS, so it does not go stale the way a cached prefix list does.
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services import bot as bot_module  # noqa: E402
from services.bot import classify_bot, reload_crawler_ranges  # noqa: E402


GOOGLE_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
INSIDE = "66.249.70.1"          # inside the prefix written below
OUTSIDE = "45.11.22.33"         # a plain address outside any Google range


def _write_ranges(directory: Path, generated_at, families=None) -> Path:
    payload = dict(families or {"googlebot": ["66.249.70.0/24"]})
    if generated_at is not None:
        payload["_meta"] = {
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "generator": "test",
        }
    path = directory / "crawler_ranges.json"
    path.write_text(json.dumps(payload))
    return path


class CrawlerRangeFreshnessTests(unittest.TestCase):
    def setUp(self):
        self._original_max_age = bot_module.RANGE_MAX_AGE_DAYS
        self.addCleanup(self._restore)

    def _restore(self):
        bot_module.RANGE_MAX_AGE_DAYS = self._original_max_age
        reload_crawler_ranges()  # back to the bundled file

    def _state(self, ip):
        return classify_bot(GOOGLE_UA, ip_address=ip)["verification_state"]

    # --- fresh data: unchanged behaviour ------------------------------------

    def test_fresh_ranges_and_matching_ip_is_verified(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), datetime.now(timezone.utc) - timedelta(days=1))
            reload_crawler_ranges(str(p))
            self.assertEqual(self._state(INSIDE), "verified")

    def test_fresh_ranges_and_non_matching_ip_is_forged(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), datetime.now(timezone.utc) - timedelta(days=1))
            reload_crawler_ranges(str(p))
            self.assertEqual(self._state(OUTSIDE), "forged")

    # --- stale data: the point of this change --------------------------------

    def test_stale_ranges_and_non_matching_ip_is_unverified_not_forged(self):
        with tempfile.TemporaryDirectory() as d:
            stale = datetime.now(timezone.utc) - timedelta(days=bot_module.RANGE_MAX_AGE_DAYS + 5)
            p = _write_ranges(Path(d), stale)
            reload_crawler_ranges(str(p))
            self.assertEqual(
                self._state(OUTSIDE), "unverified",
                "a mismatch against stale ranges must not be called forged",
            )

    def test_stale_ranges_do_not_verify_even_a_matching_ip(self):
        with tempfile.TemporaryDirectory() as d:
            stale = datetime.now(timezone.utc) - timedelta(days=bot_module.RANGE_MAX_AGE_DAYS + 5)
            p = _write_ranges(Path(d), stale)
            reload_crawler_ranges(str(p))
            self.assertEqual(
                self._state(INSIDE), "unverified",
                "a released prefix can be reallocated, so a match against stale "
                "ranges is not proof of identity either",
            )

    def test_unstamped_file_with_no_usable_mtime_is_not_trusted_for_forgery(self):
        # Provenance that cannot be established must not become an accusation.
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), None)
            import os
            old = (datetime.now(timezone.utc) - timedelta(days=400)).timestamp()
            os.utime(p, (old, old))
            reload_crawler_ranges(str(p))
            self.assertEqual(self._state(OUTSIDE), "unverified")

    # --- absent data ---------------------------------------------------------

    def test_missing_range_file_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(Path(d) / "does-not-exist.json"))
            self.assertEqual(self._state(OUTSIDE), "unverified")
            self.assertEqual(self._state(INSIDE), "unverified")

    def test_family_without_prefixes_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), datetime.now(timezone.utc), families={"googlebot": []})
            reload_crawler_ranges(str(p))
            self.assertEqual(self._state(OUTSIDE), "unverified")

    # --- the escape hatch ----------------------------------------------------

    def test_threshold_of_zero_disables_prefix_verdicts_entirely(self):
        # Zero must not be a switch for trusting a frozen file forever: that
        # would make the safest-looking value the least safe behaviour.
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), datetime.now(timezone.utc))
            reload_crawler_ranges(str(p))
            bot_module.RANGE_MAX_AGE_DAYS = 0
            self.assertEqual(self._state(OUTSIDE), "unverified")
            self.assertEqual(self._state(INSIDE), "unverified")

    def test_negative_threshold_behaves_like_zero(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), datetime.now(timezone.utc))
            reload_crawler_ranges(str(p))
            bot_module.RANGE_MAX_AGE_DAYS = -1
            self.assertEqual(self._state(INSIDE), "unverified")

    def test_fcrdns_still_verifies_against_stale_ranges(self):
        # A live DNS proof is not aged data and must survive the freshness gate.
        with tempfile.TemporaryDirectory() as d:
            stale = datetime.now(timezone.utc) - timedelta(days=4000)
            p = _write_ranges(Path(d), stale)
            reload_crawler_ranges(str(p))
            result = classify_bot(
                GOOGLE_UA, ip_address=OUTSIDE,
                fcrdns_lookup=lambda _ip: "crawl-66-249-70-1.googlebot.com",
            )
            self.assertEqual(result["verification_state"], "verified")
            self.assertEqual(result["verification_method"], "fcrdns")

    # --- the metadata key is not a crawler family ----------------------------

    def test_metadata_key_is_not_treated_as_a_family(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write_ranges(Path(d), datetime.now(timezone.utc))
            reload_crawler_ranges(str(p))
            self.assertFalse(bot_module._PREFIX_INDEX.has_family("_meta"))


def _load_fetcher():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hws_fetch_ranges", BACKEND / "scripts" / "fetch_crawler_ranges.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RefreshFailureTests(unittest.TestCase):
    """A failed refresh must leave the last known-good ranges in place."""

    def test_a_feed_returning_nothing_keeps_the_previous_prefixes(self):
        mod = _load_fetcher()

        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "crawler_ranges.json"
            # Enough prefixes per family to clear MINIMUMS on carry-forward.
            # With too few, the fetcher refuses to write at all and the stamp is
            # never reached, which is how an earlier version of this test passed
            # against the very bug it was meant to catch. A real install has
            # thousands of prefixes and does reach the write.
            previous = {family: [f"10.{n}.0.0/16" for n in range(count + 5)]
                        for family, count in mod.MINIMUMS.items()}
            previous["duckassistbot"] = ["10.200.0.0/16"]
            previous["_meta"] = {"generated_at": "2020-01-01T00:00:00Z"}
            dest.write_text(json.dumps(previous))
            import os
            os.environ["HIGASHI_CRAWLER_RANGES"] = str(dest)
            self.addCleanup(os.environ.pop, "HIGASHI_CRAWLER_RANGES", None)

            # Every feed fails. Nothing new arrives.
            def explode(*a, **k):
                raise OSError("network down")
            original = mod.urllib.request.urlopen
            mod.urllib.request.urlopen = explode
            self.addCleanup(setattr, mod.urllib.request, "urlopen", original)

            mod.main()

            after = json.loads(dest.read_text())
            for family in mod.MINIMUMS:
                self.assertEqual(
                    after.get(family), previous[family],
                    f"a total refresh failure damaged last-known-good {family}",
                )
            self.assertEqual(
                after.get("_meta", {}).get("generated_at"), "2020-01-01T00:00:00Z",
                "a failed refresh advanced the freshness stamp, which would make a "
                "box that has lost outbound access look permanently fresh while "
                "serving data that never changes",
            )

    def test_a_successful_refresh_does_advance_the_stamp(self):
        mod = _load_fetcher()
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "crawler_ranges.json"
            dest.write_text(json.dumps({
                "googlebot": ["66.249.70.0/24"],
                "_meta": {"generated_at": "2020-01-01T00:00:00Z"},
            }))
            import os
            os.environ["HIGASHI_CRAWLER_RANGES"] = str(dest)
            self.addCleanup(os.environ.pop, "HIGASHI_CRAWLER_RANGES", None)

            # Every configured feed answers with a usable prefix.
            class _Resp:
                def __enter__(self): return self
                def __exit__(self, *a): return False
                def read(self):
                    return json.dumps({"prefixes": [
                        {"ipv4Prefix": f"10.{n}.0.0/16"} for n in range(60)
                    ]}).encode()
            original = mod.urllib.request.urlopen
            mod.urllib.request.urlopen = lambda *a, **k: _Resp()
            self.addCleanup(setattr, mod.urllib.request, "urlopen", original)

            mod.main()
            after = json.loads(dest.read_text())
            self.assertNotEqual(
                after.get("_meta", {}).get("generated_at"), "2020-01-01T00:00:00Z",
                "a fully successful refresh must advance the stamp",
            )


if __name__ == "__main__":
    unittest.main()
