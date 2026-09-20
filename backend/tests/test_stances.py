"""The five stance options drive the reading and the ceiling; the old three still work.

Remove a class from a stance's `refuses`, or the legacy mapping, and a test here fails.
"""
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from higashi_reading import (  # noqa: E402
    AI_SEARCH_CAVEAT, LEGACY_TO_STANCE, SEARCH_REFUSED_CAVEAT, STANCES, ReportIn,
    crawler_class, deterministic_reading, legacy_value, max_action, stance_of,
)

CRAWLERS = [
    {"name": "Googlebot", "verified": "verified", "hits": 10, "bytes": 1, "records_taken": 0},
    {"name": "ChatGPT-User", "verified": "unverified", "hits": 4, "bytes": 1, "records_taken": 0},
    {"name": "GPTBot", "verified": "verified", "hits": 100, "bytes": 1, "records_taken": 0},
    {"name": "AhrefsBot", "verified": "unverified", "hits": 30, "bytes": 1, "records_taken": 0},
]


def report(stance=None, ai_stance="found", crawlers=CRAWLERS):
    return ReportIn.model_validate({
        "site_id": "s", "period_start": "2026-09-07", "period_end": "2026-09-13", "site_type": "shop",
        "ai_stance": ai_stance, "stance": stance, "pageviews_human": 500, "sessions_human": 300, "engaged_sessions": 10,
        "crawlers": crawlers,
        "walk": {"verdict": "No walk detected", "shape_triggered": False, "order_triggered": False,
                 "distributed_signal": False, "asset_fetch_signal": False, "per_address_rate": 1.0, "records_taken_estimate": 0},
        "geo": None,
    })


class ClassTests(unittest.TestCase):
    def test_known_names_land_in_their_class(self):
        self.assertEqual(crawler_class("Googlebot"), "search")
        self.assertEqual(crawler_class("ChatGPT-User"), "answer_fetcher")
        self.assertEqual(crawler_class("GPTBot"), "training")
        self.assertEqual(crawler_class("AhrefsBot"), "seo_tools")
        self.assertEqual(crawler_class("SomethingNew/1.0"), "other")

    def test_every_stance_has_the_copy_fields_and_a_legacy_value(self):
        for sid, st in STANCES.items():
            for key in ("label", "does", "does_not", "cost"):
                self.assertTrue(st[key], (sid, key))
            self.assertIn(st["legacy"], ("found", "search_only", "block_all"))
            self.assertEqual(legacy_value(sid), st["legacy"])


class StanceReadingTests(unittest.TestCase):
    def test_allow_all_recommends_nothing(self):
        r = report("allow_all")
        self.assertEqual(max_action(r), "none")
        self.assertNotIn("User-agent:", " ".join(deterministic_reading(r).paragraphs))

    def test_refuse_training_names_only_the_training_crawler(self):
        r = report("refuse_training")
        text = " ".join(deterministic_reading(r).paragraphs)
        self.assertEqual(max_action(r), "robots")
        self.assertIn("User-agent: GPTBot", text)
        self.assertNotIn("User-agent: AhrefsBot", text)
        self.assertNotIn("User-agent: ChatGPT-User", text)
        self.assertNotIn("User-agent: Googlebot", text)
        self.assertIn(AI_SEARCH_CAVEAT, deterministic_reading(r).paragraphs)

    def test_refuse_training_and_seo_adds_the_seo_tool(self):
        text = " ".join(deterministic_reading(report("refuse_training_seo")).paragraphs)
        self.assertIn("User-agent: GPTBot", text)
        self.assertIn("User-agent: AhrefsBot", text)
        self.assertNotIn("User-agent: ChatGPT-User", text)

    def test_keep_search_only_refuses_the_answer_fetcher_but_never_search(self):
        text = " ".join(deterministic_reading(report("keep_search_only")).paragraphs)
        self.assertIn("User-agent: ChatGPT-User", text)
        self.assertIn("User-agent: GPTBot", text)
        self.assertNotIn("User-agent: Googlebot", text)
        self.assertIn("Search is untouched", deterministic_reading(report("keep_search_only")).recommendation.reason)

    def test_refuse_all_names_search_too_and_says_what_that_costs(self):
        reading = deterministic_reading(report("refuse_all"))
        text = " ".join(reading.paragraphs)
        self.assertIn("User-agent: Googlebot", text)
        self.assertIn(SEARCH_REFUSED_CAVEAT, reading.paragraphs)
        self.assertNotIn(AI_SEARCH_CAVEAT, reading.paragraphs)
        self.assertNotIn("Search is untouched", reading.recommendation.reason)

    def test_nothing_refused_came_means_none_and_says_so(self):
        r = report("refuse_training", crawlers=CRAWLERS[:2])  # only Googlebot and ChatGPT-User
        self.assertEqual(max_action(r), "none")
        self.assertIn("None of them came", " ".join(deterministic_reading(r).paragraphs))


class LegacyTests(unittest.TestCase):
    def test_old_reports_keep_the_meaning_their_copy_had(self):
        self.assertEqual(stance_of(report(None, "found")), "allow_all")
        self.assertEqual(stance_of(report(None, "search_only")), "refuse_training")
        self.assertEqual(stance_of(report(None, "block_all")), "keep_search_only")
        self.assertEqual(set(LEGACY_TO_STANCE), {"found", "search_only", "block_all"})

    def test_explicit_stance_wins_over_the_legacy_value(self):
        self.assertEqual(stance_of(report("refuse_all", "found")), "refuse_all")

    def test_old_block_all_still_gets_robots_and_the_search_caveat(self):
        reading = deterministic_reading(report(None, "block_all"))
        self.assertTrue(any("User-agent:" in p for p in reading.paragraphs))
        self.assertIn(AI_SEARCH_CAVEAT, reading.paragraphs)


if __name__ == "__main__":
    unittest.main()
