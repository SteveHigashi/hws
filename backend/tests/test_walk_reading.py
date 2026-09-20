"""The free product explains itself: a reading with no key, no account, nothing sent.

Promises held here (remove the matching line and its test fails):
- the local reading is the same function Live runs on the same report;
- BYOK never calls Live, and falls back to the rules when the key is missing, the
  model fails, or the model writes outside the rules;
- the rules are the ceiling for BYOK prose.
"""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent / "live"))  # Live's copy of the rules, for the identity test

from higashi_reading import AI_SEARCH_CAVEAT, ReadingBody, ReportIn, deterministic_reading  # noqa: E402
from services import walk_reading  # noqa: E402

REPORT = {
    "site_id": "site-one",
    "period_start": "2026-09-07",
    "period_end": "2026-09-13",
    "site_type": "shop",
    "ai_stance": "block_all",
    "pageviews_human": 5000,
    "sessions_human": 3000,
    "engaged_sessions": 1200,
    "crawlers": [
        {"name": "GPTBot", "verified": "verified", "hits": 100, "bytes": 50000, "records_taken": 20},
        {"name": "Bytespider", "verified": "unverified", "hits": 40, "bytes": 9000, "records_taken": 0},
    ],
    "walk": {
        "verdict": "Suspicious", "shape_triggered": True, "order_triggered": False,
        "distributed_signal": False, "asset_fetch_signal": False,
        "per_address_rate": 12.5, "records_taken_estimate": 0,
    },
    "geo": None,
}


def _model_json(**overrides):
    body = {
        "headline": "Two AI crawlers came this week",
        "paragraphs": ["GPTBot made 100 hits. Bytespider made 40.", "User-agent: GPTBot\nDisallow: /"],
        "verdict": "Suspicious",
        "changes": [],
        "benchmarks": [],
    }
    body.update(overrides)
    return json.dumps(body)


class LocalReadingTests(unittest.TestCase):
    def test_local_reading_needs_no_key_and_carries_the_caveat_and_robots_block(self):
        reading = walk_reading.local_reading(REPORT)
        self.assertIsInstance(reading, ReadingBody)
        self.assertIn(AI_SEARCH_CAVEAT, reading.paragraphs)
        self.assertTrue(any("User-agent: GPTBot" in p for p in reading.paragraphs))
        self.assertTrue(any("bytespider" in p.casefold() and "ignore robots.txt" in p for p in reading.paragraphs))
        self.assertTrue(any("Higashi reports what arrived" in p for p in reading.paragraphs))
        self.assertTrue(any("needs Higashi Live" in p for p in reading.paragraphs))

    def test_local_reading_is_the_same_function_live_runs(self):
        from app import reading as live_reading  # Live's module, importing the same package
        report = ReportIn.model_validate(REPORT)
        from higashi_reading import no_comparison_notes
        ours = deterministic_reading(report, product="Live")
        theirs = live_reading.deterministic_reading(report, [], [], no_comparison_notes(report))
        self.assertEqual(ours.headline, theirs.headline)
        self.assertEqual(ours.verdict, theirs.verdict)
        self.assertEqual(ours.paragraphs, theirs.paragraphs)


class ByokReadingTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_key_falls_back_to_the_rules_and_says_so(self):
        with patch.object(walk_reading, "call_model") as call:
            reading, used, note = await walk_reading.byok_reading(REPORT, "claude-haiku-4-5-20251001", {"anthropic": ""})
        call.assert_not_called()
        self.assertEqual(used, "local")
        self.assertIn("No anthropic key", note)
        self.assertEqual(reading, walk_reading.local_reading(REPORT))

    async def test_model_prose_is_used_when_it_stays_inside_the_rules(self):
        async def fake_call(model, system, user, api_keys, **_):
            return _model_json(), 10, 20
        with patch.object(walk_reading, "call_model", fake_call):
            reading, used, note = await walk_reading.byok_reading(REPORT, "claude-haiku-4-5-20251001", {"anthropic": "k"})
        self.assertEqual(used, "byok")
        self.assertIsNone(note)
        self.assertEqual(reading.headline, "Two AI crawlers came this week")

    async def test_model_claiming_higashi_blocked_traffic_is_replaced_by_the_rules(self):
        async def fake_call(model, system, user, api_keys, **_):
            return _model_json(paragraphs=["Higashi blocked GPTBot for you.", "User-agent: GPTBot\nDisallow: /"]), 10, 20
        with patch.object(walk_reading, "call_model", fake_call):
            reading, used, note = await walk_reading.byok_reading(REPORT, "claude-haiku-4-5-20251001", {"anthropic": "k"})
        self.assertEqual(used, "local")
        self.assertIn("outside the rules", note)
        self.assertEqual(reading, walk_reading.local_reading(REPORT))

    async def test_model_inventing_a_benchmark_is_replaced_by_the_rules(self):
        async def fake_call(model, system, user, api_keys, **_):
            return _model_json(paragraphs=["GPTBot hit you 100 times. Typical for a site your size is 20.", "User-agent: GPTBot\nDisallow: /"]), 10, 20
        with patch.object(walk_reading, "call_model", fake_call):
            _reading, used, _note = await walk_reading.byok_reading(REPORT, "claude-haiku-4-5-20251001", {"anthropic": "k"})
        self.assertEqual(used, "local")

    async def test_model_failure_never_raises(self):
        async def fake_call(*_a, **_k):
            raise RuntimeError("quota")
        with patch.object(walk_reading, "call_model", fake_call):
            reading, used, note = await walk_reading.byok_reading(REPORT, "claude-haiku-4-5-20251001", {"anthropic": "k"})
        self.assertEqual(used, "local")
        self.assertIn("did not answer", note)

    async def test_byok_never_talks_to_live(self):
        async def fake_call(*_a, **_k):
            return _model_json(), 1, 1
        with patch.object(walk_reading, "call_model", fake_call), \
             patch("services.live_client.send_report") as send:
            await walk_reading.byok_reading(REPORT, "claude-haiku-4-5-20251001", {"anthropic": "k"})
            walk_reading.local_reading(REPORT)
        send.assert_not_called()


class RouterWiringTests(unittest.TestCase):
    def test_reading_route_is_mounted_and_defaults_to_local(self):
        import main
        paths = {r.path for r in main.app.routes}
        self.assertIn("/api/reading", paths)
        from config import Settings
        self.assertEqual(Settings().walk_reading_provider, "local")


if __name__ == "__main__":
    unittest.main()
