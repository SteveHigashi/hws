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


# ── no customer ever reads an internal stance value ──────────────────────────
import json  # noqa: E402

from higashi_reading import (  # noqa: E402
    ENFORCEMENT_CLAIMS, RAW_STANCE_TOKENS, SYSTEM_PROMPT, ReadingBody,
    constrain_model_reading, enforcement_claim_in, model_context, raw_stance_token_in,
    stance_context,
)


def reading_saying(text):
    return ReadingBody.model_validate({
        "headline": "Nothing unusual this week", "paragraphs": [text],
        "verdict": "No walk detected", "changes": [], "benchmarks": [],
    })


class StanceStaysInternalTests(unittest.TestCase):
    """`search_only` in a reading is jargon the reader cannot act on.

    Two defences, because asking a model nicely is not a control: the values are
    stripped from what the model is shown, and a reading naming one is refused.
    Remove either and a test here fails.
    """

    def test_the_context_shown_to_the_model_contains_no_internal_value(self):
        for stance in STANCES:
            blob = json.dumps(model_context(report(stance, legacy_value(stance)), [], [], [])).casefold()
            for token in RAW_STANCE_TOKENS:
                self.assertNotIn(token, blob, f"{token} leaked into the model context for {stance}")

    def test_the_context_carries_the_approved_label_instead(self):
        for stance, spec in STANCES.items():
            ctx = model_context(report(stance, legacy_value(stance)), [], [], [])
            self.assertEqual(ctx["stance"]["chose"], spec["label"])
            self.assertEqual(ctx["stance"]["does_not_mean"], spec["does_not"])

    def test_a_reading_naming_an_internal_value_is_refused(self):
        r = report("refuse_training", "search_only")
        fallback = deterministic_reading(r)
        leaked = reading_saying("Your site chose search_only, so training crawlers are refused.")
        self.assertEqual(raw_stance_token_in(leaked), "search_only")
        self.assertIs(constrain_model_reading(leaked, fallback, r, [], []), fallback)

    def test_every_internal_value_is_caught(self):
        r = report("refuse_training", "search_only")
        fallback = deterministic_reading(r)
        for token in RAW_STANCE_TOKENS:
            leaked = reading_saying(f"The owner picked {token} this week.")
            self.assertIs(constrain_model_reading(leaked, fallback, r, [], []), fallback, token)

    def test_the_word_found_is_ordinary_prose_and_is_not_refused(self):
        """`found` is a legacy value and an English word; banning it would reject good prose."""
        r = report("allow_all", "found")
        fallback = deterministic_reading(r)
        fine = reading_saying("Higashi found 900 visits from training crawlers this week.")
        self.assertIsNone(raw_stance_token_in(fine))
        self.assertIsNot(constrain_model_reading(fine, fallback, r, [], []), fallback)

    def test_the_approved_labels_survive_the_ban(self):
        """The labels must not themselves trip the check that protects them."""
        r = report("refuse_training", "search_only")
        fallback = deterministic_reading(r)
        for spec in STANCES.values():
            self.assertIsNone(raw_stance_token_in(reading_saying(f"You chose: {spec['label']}.")), spec["label"])
        self.assertIsNot(constrain_model_reading(
            reading_saying("You chose Refuse training crawlers."), fallback, r, [], []), fallback)

    def test_the_prompt_tells_the_model_the_vocabulary_and_forbids_the_values(self):
        self.assertIn("stance", SYSTEM_PROMPT)
        self.assertIn("training crawlers", SYSTEM_PROMPT)
        self.assertIn("Never print an internal value", SYSTEM_PROMPT)

    def test_stance_context_names_what_is_refused_and_what_is_allowed(self):
        ctx = stance_context(report("keep_search_only", "block_all"))
        self.assertIn("search crawlers", ctx["allows"])
        self.assertIn("training crawlers", ctx["refuses"])
        self.assertNotIn("search crawlers", ctx["refuses"])


class ReadingShapeTests(unittest.TestCase):
    """Three defects the 2026-09-23 Live deploy printed, each with the real text.

    The model is asked for prose; it is not the authority on the verdict, on what the
    headline is for, or on what Higashi does to a crawler. Remove any one of the three
    controls in prompt.py and a test here fails.
    """

    def setUp(self):
        self.report = report("refuse_training", "search_only")
        self.fallback = deterministic_reading(self.report)

    def reading(self, **over):
        body = {"headline": "GPTBot took 420 records this week", "paragraphs": ["Plain prose."],
                "verdict": "Suspicious", "changes": [], "benchmarks": []}
        body.update(over)
        return ReadingBody.model_validate(body)

    # 1 — the verdict is data
    def test_a_sentence_in_the_verdict_is_replaced_by_the_walk_verdict(self):
        wordy = self.reading(verdict="Suspicious activity detected from training crawler. "
                                     "Owner refuses training crawlers while allowing search.")
        out = constrain_model_reading(wordy, self.fallback, self.report, [], [])
        self.assertEqual(out.verdict, self.report.walk.verdict)

    def test_the_verdict_is_always_one_of_the_four(self):
        allowed = {"Catalogue walk detected", "Suspicious", "No walk detected", "Insufficient data"}
        for invented in ("Suspicious-ish", "All clear!", "", "Suspicious activity detected"):
            out = constrain_model_reading(self.reading(verdict=invented), self.fallback, self.report, [], [])
            self.assertIn(out.verdict, allowed)

    # 2 — the headline is the finding, not the setting
    def test_the_prompt_forbids_a_headline_that_is_the_owners_own_setting(self):
        self.assertIn("Never make the headline the owner's own setting", SYSTEM_PROMPT)
        self.assertIn("what happened this week", SYSTEM_PROMPT)

    # 3 — nothing is enforced
    def test_the_promise_that_a_crawler_cannot_fetch_is_refused(self):
        leaked = self.reading(paragraphs=[
            "The owner chose to refuse training crawlers. This means GPTBot, ClaudeBot, "
            "Bytespider and CCBot will not be able to fetch pages."])
        self.assertEqual(enforcement_claim_in(leaked), "will not be able to")
        self.assertIs(constrain_model_reading(leaked, self.fallback, self.report, [], []), self.fallback)

    def test_every_enforcement_claim_is_caught_wherever_it_appears(self):
        for claim in ENFORCEMENT_CLAIMS:
            for where in ("headline", "paragraphs", "recommendation"):
                if where == "paragraphs":
                    r = self.reading(paragraphs=[f"GPTBot {claim} the site."])
                elif where == "headline":
                    r = self.reading(headline=f"GPTBot {claim} the site")
                else:
                    r = self.reading(recommendation={"action": "robots",
                                                     "reason": f"GPTBot {claim} the site.",
                                                     "confidence": "low"})
                self.assertIs(constrain_model_reading(r, self.fallback, self.report, [], []),
                              self.fallback, f"{claim} in {where}")

    def test_honest_conditional_wording_is_kept(self):
        """"Where you enforce it" is the true sentence and must survive the check."""
        for good in ("You can refuse training crawlers in robots.txt.",
                     "Where you enforce the refusal, training crawlers cannot fetch those pages.",
                     "The rule would ask them not to fetch; a crawler that ignores robots.txt keeps coming."):
            r = self.reading(paragraphs=[good])
            self.assertIsNone(enforcement_claim_in(r), good)

    def test_the_prompt_says_nothing_is_enforced(self):
        self.assertIn("Nothing here is enforced", SYSTEM_PROMPT)
        self.assertIn("where you enforce it", SYSTEM_PROMPT)

    def test_a_qualifier_elsewhere_does_not_excuse_an_unqualified_claim(self):
        """Judged per sentence. One honest sentence must not license a false one."""
        mixed = self.reading(paragraphs=[
            "Where you enforce the refusal, training crawlers cannot fetch those pages.",
            "GPTBot will not be able to fetch pages.",
        ])
        self.assertEqual(enforcement_claim_in(mixed), "will not be able to")
        self.assertIs(constrain_model_reading(mixed, self.fallback, self.report, [], []), self.fallback)

    def test_a_qualified_claim_survives_constrain_not_just_the_helper(self):
        honest = self.reading(paragraphs=[
            "Where you enforce the refusal, training crawlers cannot fetch those pages."])
        self.assertIsNot(constrain_model_reading(honest, self.fallback, self.report, [], []), self.fallback)
