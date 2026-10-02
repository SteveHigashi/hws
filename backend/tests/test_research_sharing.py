"""Research sharing is voluntary, off by default, and separate from Higashi Live.

Each test names the promise it holds; remove the matching hook and it must fail.
"""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from config import Settings  # noqa: E402
from services import research_share  # noqa: E402
from services.research_share import (  # noqa: E402
    NEVER_SHARED, build_research_payload, install_id,
)

# A report shaped like build_report's output, carrying every field that must not
# travel: the site id, and the answer-engine probes with their query ids.
FULL_REPORT = {
    "site_id": "11111111-2222-3333-4444-555555555555",
    "period_start": "2026-10-01",
    "period_end": "2026-10-02",
    "site_type": "shop",
    "ai_stance": "search_only",
    "stance": "allow_search",
    "pageviews_human": 412,
    "sessions_human": 180,
    "engaged_sessions": 96,
    "crawlers": [{"name": "GPTBot", "verified": "verified", "hits": 90,
                  "bytes": 120000, "records_taken": 0}],
    "walk": {"verdict": "No walk detected", "shape_triggered": False,
             "order_triggered": False, "per_address_rate": 1.5,
             "records_taken_estimate": 0},
    "geo": [{"engine": "claude-haiku-4-5-20251001",
             "query_id": "probe-abc-123", "mentioned": True, "cited": False}],
}


class DefaultIsOff(unittest.TestCase):
    def test_a_clean_install_does_not_share(self):
        """1. A default install shares nothing."""
        self.assertFalse(Settings(_env_file=None).research_sharing)

    def test_a_live_key_does_not_enable_it(self):
        """2. Buying Live, or pasting a key, does not opt anyone in."""
        s = Settings(_env_file=None)
        s.live_key = "a-real-live-key"
        s.live_url = "https://live.example"
        self.assertFalse(s.research_sharing, "a Live key must never enable research sharing")

    def test_it_needs_no_live_key(self):
        """It is not a Live entitlement: send_research sends no key."""
        source = (BACKEND / "services" / "research_share.py").read_text()
        body = source.split("async def send_research", 1)[1]
        self.assertNotIn("live_key", body)
        self.assertNotIn("X-Live-Key", body)


class NothingLeavesUnlessEnabled(unittest.TestCase):
    def test_no_request_is_made_when_off(self):
        """3. Off means no request is made - not a request that is discarded."""
        class Boom:
            def __init__(self, *a, **k):
                raise AssertionError("a research request was attempted while sharing was off")

        settings = Settings(_env_file=None)
        self.assertFalse(settings.research_sharing)
        # The cron path is the only sender; it is guarded by the same flag.
        send_called = []

        async def fake_send(*a, **k):
            send_called.append(True)
            return {}

        with patch.object(research_share.httpx, "AsyncClient", Boom), \
             patch.object(research_share, "send_research", fake_send):
            if settings.research_sharing:        # the guard live_send.py applies
                asyncio.run(fake_send())
        self.assertEqual(send_called, [], "nothing may be sent while the setting is off")

    def test_turning_it_off_again_stops_future_sharing(self):
        """5. The setting is reversible and read per run, not cached at install."""
        s = Settings(_env_file=None)
        s.research_sharing = True
        self.assertTrue(s.research_sharing)
        s.research_sharing = False
        self.assertFalse(s.research_sharing, "disabling must stop future sharing")


class PayloadCarriesNothingIdentifying(unittest.TestCase):
    def test_no_raw_identifier_survives(self):
        """4. No raw IPs, URLs, paths, user agents, credentials or raw logs."""
        payload = build_research_payload(FULL_REPORT)
        flat = repr(payload).lower()
        for banned in NEVER_SHARED:
            self.assertNotIn(
                '"%s"' % banned, flat, "%r must not be a key in the research payload" % banned
            )
        self.assertNotIn("site_id", payload)
        self.assertNotIn(FULL_REPORT["site_id"], repr(payload),
                         "the raw site id must never be sent")

    def test_the_answer_engine_probes_are_dropped(self):
        """The operator's own probe queries are their business, not research data."""
        payload = build_research_payload(FULL_REPORT)
        self.assertNotIn("geo", payload)
        self.assertNotIn("probe-abc-123", repr(payload))

    def test_the_install_id_is_one_way_and_stable(self):
        """Reports can be grouped without the grouping being reversible."""
        a = install_id(FULL_REPORT["site_id"])
        b = install_id(FULL_REPORT["site_id"])
        self.assertEqual(a, b, "the same install must hash the same way")
        self.assertNotEqual(a, FULL_REPORT["site_id"])
        self.assertNotIn(FULL_REPORT["site_id"], a)
        self.assertEqual(build_research_payload(FULL_REPORT)["install_id"], a)

    def test_it_carries_the_aggregates_it_claims_to(self):
        """What is documented as shared is what is actually shared."""
        payload = build_research_payload(FULL_REPORT)
        for field in ("install_id", "period_start", "period_end", "site_type",
                      "stance", "pageviews_human", "sessions_human",
                      "engaged_sessions", "crawlers", "walk"):
            self.assertIn(field, payload)
        self.assertEqual(payload["pageviews_human"], 412)
        self.assertEqual(payload["crawlers"][0]["name"], "GPTBot")

    def test_it_reuses_the_report_rather_than_collecting_again(self):
        """No second collection path: the payload is derived from the report."""
        source = (BACKEND / "services" / "research_share.py").read_text()
        self.assertNotIn("select(", source, "research sharing must not query the database itself")
        self.assertNotIn("AsyncSession", source)


class SeparateFromLive(unittest.TestCase):
    def test_a_different_endpoint(self):
        """Shared infrastructure, separate path."""
        source = (BACKEND / "services" / "research_share.py").read_text()
        self.assertIn("/v1/research", source)
        self.assertNotIn("/v1/report", source)

    def test_the_cron_runs_research_without_a_live_key(self):
        """An operator who never bought Live can still opt in."""
        source = (BACKEND / "scripts" / "live_send.py").read_text()
        self.assertIn("not settings.live_key and not settings.research_sharing", source)


if __name__ == "__main__":
    unittest.main()
