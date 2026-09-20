"""The rules set the maximum action; a model can write the reason, never raise the action.

Remove a branch of max_action() or the rank check in clamp_recommendation() and a
test here fails.
"""
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from higashi_reading import (  # noqa: E402
    ACTIONS, ReadingBody, Recommendation, ReportIn, action_rank, clamp_recommendation,
    constrain_model_reading, deterministic_reading, deterministic_recommendation, max_action,
)

BASE = {
    "site_id": "s", "period_start": "2026-09-07", "period_end": "2026-09-13", "site_type": "shop",
    "ai_stance": "search_only", "pageviews_human": 5000, "sessions_human": 3000, "engaged_sessions": 100,
    "crawlers": [
        {"name": "GPTBot", "verified": "verified", "hits": 100, "bytes": 5, "records_taken": 20},
        {"name": "Googlebot", "verified": "verified", "hits": 10, "bytes": 5, "records_taken": 0},
    ],
    "walk": {"verdict": "No walk detected", "shape_triggered": False, "order_triggered": False,
             "distributed_signal": False, "asset_fetch_signal": False, "per_address_rate": 1.0, "records_taken_estimate": 0},
    "geo": None,
}


def report(**walk_or_top):
    body = dict(BASE)
    walk = dict(BASE["walk"])
    for k, v in walk_or_top.items():
        (walk if k in walk else body).__setitem__(k, v)
    body["walk"] = walk
    return ReportIn.model_validate(body)


def model_rec(action, reason="The model's own sentence about the step."):
    return Recommendation(action=action, reason=reason, confidence="high")


class CeilingTests(unittest.TestCase):
    def test_insufficient_data_allows_nothing(self):
        self.assertEqual(max_action(report(verdict="Insufficient data")), "none")

    def test_suspicious_with_no_records_is_observe_at_most(self):
        self.assertEqual(max_action(report(verdict="Suspicious", records_taken_estimate=0)), "observe")

    def test_suspicious_with_records_is_robots_at_most(self):
        self.assertEqual(max_action(report(verdict="Suspicious", records_taken_estimate=50)), "robots")

    def test_detected_distributed_walk_is_rate_rule_not_block(self):
        self.assertEqual(max_action(report(verdict="Catalogue walk detected", records_taken_estimate=4000, distributed_signal=True)), "rate_rule")

    def test_detected_single_source_walk_may_be_blocked(self):
        self.assertEqual(max_action(report(verdict="Catalogue walk detected", records_taken_estimate=4000, per_address_rate=40.0)), "block_rule")

    def test_detected_walk_with_zero_records_is_observe(self):
        self.assertEqual(max_action(report(verdict="Catalogue walk detected", records_taken_estimate=0)), "observe")

    def test_no_walk_and_owner_welcomes_ai_means_none(self):
        self.assertEqual(max_action(report(ai_stance="found")), "none")

    def test_no_walk_but_training_crawlers_unwelcome_allows_robots(self):
        self.assertEqual(max_action(report(ai_stance="search_only")), "robots")
        self.assertEqual(max_action(report(ai_stance="block_all")), "robots")

    def test_forged_crawler_alone_is_observe(self):
        r = report(ai_stance="found")
        r = r.model_copy(update={"crawlers": [r.crawlers[0].model_copy(update={"verified": "forged"})]})
        self.assertEqual(max_action(r), "observe")

    def test_rules_recommendation_never_exceeds_the_ceiling(self):
        for verdict in ("Insufficient data", "No walk detected", "Suspicious", "Catalogue walk detected"):
            for records in (0, 50, 4000):
                for distributed in (False, True):
                    r = report(verdict=verdict, records_taken_estimate=records, distributed_signal=distributed)
                    rec = deterministic_recommendation(r)
                    self.assertLessEqual(action_rank(rec.action), action_rank(max_action(r)), (verdict, records, distributed))
                    self.assertTrue(rec.reason)
                    if rec.action != "none":
                        self.assertTrue(rec.rollback, rec.action)


class ClampTests(unittest.TestCase):
    def test_model_asking_for_more_than_the_evidence_is_clamped_to_the_rules(self):
        r = report(verdict="Suspicious", records_taken_estimate=0)  # ceiling: observe
        for too_much in ("robots", "rate_rule", "block_rule"):
            out = clamp_recommendation(model_rec(too_much), r)
            self.assertEqual(out.action, "observe", too_much)
            self.assertEqual(out.reason, deterministic_recommendation(r).reason)  # its reason is dropped too

    def test_model_choosing_less_keeps_its_reason_and_gets_the_rules_structure(self):
        r = report(verdict="Catalogue walk detected", records_taken_estimate=4000, per_address_rate=40.0)  # ceiling: block_rule
        out = clamp_recommendation(model_rec("rate_rule", "Slow it down first; that is enough here."), r)
        self.assertEqual(out.action, "rate_rule")
        self.assertEqual(out.reason, "Slow it down first; that is enough here.")
        self.assertEqual(out.exclusions, deterministic_recommendation(r).exclusions)
        self.assertIn("rate rule", out.rollback)

    def test_model_with_no_recommendation_gets_the_rules_one(self):
        r = report()
        self.assertEqual(clamp_recommendation(None, r), deterministic_recommendation(r))

    def test_an_empty_or_bloated_reason_is_replaced(self):
        r = report()
        self.assertEqual(clamp_recommendation(model_rec("none", " "), r).reason, deterministic_recommendation(r).reason)
        self.assertEqual(clamp_recommendation(model_rec("none", "word " * 90), r).reason, deterministic_recommendation(r).reason)

    def test_the_whole_model_reading_passes_through_the_clamp(self):
        r = report(verdict="Insufficient data")  # ceiling: none
        fallback = deterministic_reading(r)
        model = ReadingBody(headline="Block them all", paragraphs=["Something happened."], verdict="Insufficient data",
                            changes=[], benchmarks=[], recommendation=model_rec("block_rule"))
        out = constrain_model_reading(model, fallback, r, [], [])
        self.assertEqual(out.recommendation.action, "none")

    def test_every_action_has_a_rank_in_order(self):
        self.assertEqual([action_rank(a) for a in ACTIONS], list(range(len(ACTIONS))))


if __name__ == "__main__":
    unittest.main()
