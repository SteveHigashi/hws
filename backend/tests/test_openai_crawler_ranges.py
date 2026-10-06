"""OpenAI crawler identities verify against OpenAI's own published prefixes.

OpenAI publishes one feed per crawler purpose, so each identity is checked
against its own feed rather than a shared pool: an address that is legitimate
for ChatGPT-User is not thereby legitimate for GPTBot.

These pin the wiring that is easy to get subtly wrong. The verifier reaches
crawler_ranges.json through _NETWORK_RULES, keyed by the exact string the
classifier produces, so a feed added without a matching rule, or a rule whose
key does not match the classifier, is inert and every claim silently reads
unverified. The names are asserted against the classifier rather than hardcoded
hopes.

Anthropic publishes no authoritative prefix feed, so ClaudeBot must stay
recognised and unverified. A test pins that too, so nobody later wires it to a
third-party list to make the catalogue look complete.
"""

import importlib.util
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

UA = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
              "GPTBot/1.2; +https://openai.com/gptbot",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
                     "OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
                    "ChatGPT-User/1.0; +https://openai.com/bot",
}
FAMILY = {"GPTBot": "gptbot", "OAI-SearchBot": "oai-searchbot", "ChatGPT-User": "chatgpt-user"}
PREFIX = {"gptbot": "132.196.86.0/24", "oai-searchbot": "104.210.140.128/28",
          "chatgpt-user": "104.208.184.192/28"}
INSIDE = {"gptbot": "132.196.86.7", "oai-searchbot": "104.210.140.130",
          "chatgpt-user": "104.208.184.194"}
OUTSIDE = "45.11.22.33"


def _load_fetcher():
    spec = importlib.util.spec_from_file_location(
        "hws_fetch_ranges_openai", BACKEND / "scripts" / "fetch_crawler_ranges.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(directory: Path, age_days: float) -> Path:
    payload = {fam: [PREFIX[fam]] for fam in PREFIX}
    stamp = datetime.now(timezone.utc) - timedelta(days=age_days)
    payload["_meta"] = {"generated_at": stamp.isoformat().replace("+00:00", "Z")}
    path = directory / "crawler_ranges.json"
    path.write_text(json.dumps(payload))
    return path


class OpenAIWiringTests(unittest.TestCase):
    """The classifier's names and the network rules must agree exactly."""

    def test_each_openai_identity_is_recognised_and_wired(self):
        for name, ua in UA.items():
            with self.subTest(crawler=name):
                result = classify_bot(ua)
                self.assertIsNotNone(result, f"{name} is not recognised at all")
                self.assertEqual(result["name"], name)
                rule = bot_module._NETWORK_RULES.get(result["name"])
                self.assertIsNotNone(
                    rule, f"{name} has no network rule, so it can never verify")
                self.assertEqual(
                    rule["groups"], (FAMILY[name],),
                    f"{name} is wired to the wrong range family")

    def test_the_fetcher_publishes_a_feed_for_each_wired_family(self):
        mod = _load_fetcher()
        for family in FAMILY.values():
            with self.subTest(family=family):
                self.assertIn(family, mod.FEEDS, f"no feed configured for {family}")
                self.assertIn(family, mod.MINIMUMS, f"no MINIMUMS floor for {family}")

    def test_the_official_openai_urls_are_used(self):
        mod = _load_fetcher()
        self.assertEqual(mod.FEEDS["gptbot"], ["https://openai.com/gptbot.json"])
        self.assertEqual(mod.FEEDS["oai-searchbot"], ["https://openai.com/searchbot.json"])
        self.assertEqual(mod.FEEDS["chatgpt-user"], ["https://openai.com/chatgpt-user.json"])
        # The crawler is called OAI-SearchBot but the feed is searchbot.json.
        # oai-searchbot.json does not exist and must never be used.
        self.assertNotIn(
            "https://openai.com/oai-searchbot.json",
            [u for urls in mod.FEEDS.values() for u in urls],
        )


class OpenAIVerdictTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(reload_crawler_ranges)

    def _state(self, name, ip, **kw):
        return classify_bot(UA[name], ip_address=ip, **kw)["verification_state"]

    def test_fresh_ranges_verify_an_in_range_address(self):
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(_write(Path(d), 1)))
            for name in UA:
                with self.subTest(crawler=name):
                    self.assertEqual(self._state(name, INSIDE[FAMILY[name]]), "verified")

    def test_fresh_ranges_call_an_out_of_range_address_forged(self):
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(_write(Path(d), 1)))
            for name in UA:
                with self.subTest(crawler=name):
                    self.assertEqual(self._state(name, OUTSIDE), "forged")

    def test_each_feed_is_checked_separately(self):
        # A ChatGPT-User address is not evidence for a GPTBot claim.
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(_write(Path(d), 1)))
            self.assertEqual(self._state("GPTBot", INSIDE["chatgpt-user"]), "forged")
            self.assertEqual(self._state("ChatGPT-User", INSIDE["gptbot"]), "forged")

    def test_stale_ranges_do_not_verify_a_matching_address(self):
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(_write(Path(d), bot_module.RANGE_MAX_AGE_DAYS + 5)))
            for name in UA:
                with self.subTest(crawler=name):
                    self.assertEqual(self._state(name, INSIDE[FAMILY[name]]), "unverified")

    def test_stale_ranges_do_not_accuse_a_non_matching_address(self):
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(_write(Path(d), bot_module.RANGE_MAX_AGE_DAYS + 5)))
            for name in UA:
                with self.subTest(crawler=name):
                    self.assertEqual(self._state(name, OUTSIDE), "unverified")

    def test_missing_range_data_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(Path(d) / "absent.json"))
            for name in UA:
                with self.subTest(crawler=name):
                    self.assertEqual(self._state(name, INSIDE[FAMILY[name]]), "unverified")

    def test_fcrdns_remains_an_independent_path(self):
        # Googlebot publishes a reverse-DNS contract; that path must still verify
        # on its own, including against ranges too stale to decide anything.
        with tempfile.TemporaryDirectory() as d:
            reload_crawler_ranges(str(_write(Path(d), bot_module.RANGE_MAX_AGE_DAYS + 5)))
            google = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            result = classify_bot(
                google, ip_address=OUTSIDE,
                fcrdns_lookup=lambda _ip: "crawl-66-249-70-1.googlebot.com")
            self.assertEqual(result["verification_state"], "verified")
            self.assertEqual(result["verification_method"], "fcrdns")

    def test_openai_has_no_invented_reverse_dns_contract(self):
        # OpenAI publishes no PTR contract. Claiming one would manufacture
        # evidence, so the rules must carry no suffixes for these names.
        for name in UA:
            with self.subTest(crawler=name):
                self.assertEqual(bot_module._NETWORK_RULES[name]["suffixes"], ())


class AnthropicStaysUnverifiedTests(unittest.TestCase):
    def test_claudebot_is_recognised_but_has_no_network_rule(self):
        result = classify_bot("Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)")
        self.assertEqual(result["name"], "ClaudeBot")
        self.assertNotIn(
            "ClaudeBot", bot_module._NETWORK_RULES,
            "Anthropic publishes no authoritative prefix feed. ClaudeBot must stay "
            "recognised and unverified rather than be wired to a third-party list.",
        )

    def test_claudebot_reads_unverified_not_forged(self):
        self.assertEqual(
            classify_bot("Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
                         ip_address=OUTSIDE)["verification_state"],
            "unverified",
        )


class AhrefsOfficialFeedTests(unittest.TestCase):
    """Ahrefs publishes an official prefix feed in the same shape as the rest."""

    AHREFS_UA = "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)"

    def setUp(self):
        self.addCleanup(reload_crawler_ranges)

    def test_ahrefsbot_is_recognised_and_wired_to_its_own_feed(self):
        result = classify_bot(self.AHREFS_UA)
        self.assertEqual(result["name"], "AhrefsBot")
        rule = bot_module._NETWORK_RULES.get("AhrefsBot")
        self.assertIsNotNone(rule, "AhrefsBot has no network rule")
        self.assertEqual(rule["groups"], ("ahrefsbot",))
        self.assertEqual(rule["suffixes"], (), "no reverse-DNS contract is published")
        mod = _load_fetcher()
        self.assertEqual(
            mod.FEEDS["ahrefsbot"], ["https://api.ahrefs.com/v3/public/crawler-ip-ranges"])
        self.assertIn("ahrefsbot", mod.MINIMUMS)

    def test_fresh_ahrefs_ranges_decide_both_ways(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "crawler_ranges.json"
            stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            path.write_text(json.dumps({
                "ahrefsbot": ["5.39.1.224/27"],
                "_meta": {"generated_at": stamp},
            }))
            reload_crawler_ranges(str(path))
            self.assertEqual(
                classify_bot(self.AHREFS_UA, ip_address="5.39.1.230")["verification_state"],
                "verified")
            self.assertEqual(
                classify_bot(self.AHREFS_UA, ip_address=OUTSIDE)["verification_state"],
                "forged")

    def test_the_live_ahrefs_feed_parses(self):
        import urllib.error, urllib.request
        mod = _load_fetcher()
        url = mod.FEEDS["ahrefsbot"][0]
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Higashi-range-refresh/1.0"})
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            self.skipTest(f"network unavailable: {exc}")
        prefixes = mod._prefixes(payload)
        self.assertGreaterEqual(len(prefixes), mod.MINIMUMS["ahrefsbot"])


class OpenAIRefreshFailureTests(unittest.TestCase):
    def test_failure_keeps_openai_prefixes_and_does_not_restamp(self):
        mod = _load_fetcher()
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "crawler_ranges.json"
            previous = {family: [f"10.{n}.0.0/16" for n in range(count + 5)]
                        for family, count in mod.MINIMUMS.items()}
            previous["duckassistbot"] = ["10.200.0.0/16"]
            previous["_meta"] = {"generated_at": "2020-01-01T00:00:00Z"}
            dest.write_text(json.dumps(previous))

            import os
            os.environ["HIGASHI_CRAWLER_RANGES"] = str(dest)
            self.addCleanup(os.environ.pop, "HIGASHI_CRAWLER_RANGES", None)

            original = mod.urllib.request.urlopen
            mod.urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(OSError("down"))
            self.addCleanup(setattr, mod.urllib.request, "urlopen", original)

            mod.main()
            after = json.loads(dest.read_text())
            for family in FAMILY.values():
                with self.subTest(family=family):
                    self.assertEqual(after.get(family), previous[family],
                                     f"a failed refresh damaged {family}")
            self.assertEqual(
                after.get("_meta", {}).get("generated_at"), "2020-01-01T00:00:00Z",
                "carried-forward OpenAI data must not receive a new freshness stamp",
            )


class LiveOpenAIFeedTests(unittest.TestCase):
    """The published feeds must still exist and still parse.

    This reaches the network on purpose. A feed that moves or changes shape is
    exactly the failure these tests exist to catch, and it cannot be caught with
    a fixture. Skipped rather than failed when the network is unavailable.
    """

    def test_the_live_feeds_parse_and_carry_usable_prefixes(self):
        import urllib.error
        import urllib.request
        mod = _load_fetcher()
        for family in FAMILY.values():
            url = mod.FEEDS[family][0]
            with self.subTest(family=family):
                try:
                    request = urllib.request.Request(
                        url, headers={"User-Agent": "Higashi-range-refresh/1.0"})
                    with urllib.request.urlopen(request, timeout=25) as response:
                        payload = json.loads(response.read().decode())
                except (urllib.error.URLError, OSError, TimeoutError) as exc:
                    self.skipTest(f"network unavailable for {url}: {exc}")
                prefixes = mod._prefixes(payload)
                self.assertGreaterEqual(
                    len(prefixes), mod.MINIMUMS[family],
                    f"{url} returned {len(prefixes)} prefixes, below the "
                    f"MINIMUMS floor of {mod.MINIMUMS[family]}",
                )
                import ipaddress
                for prefix in prefixes[:5]:
                    ipaddress.ip_network(prefix, strict=False)


if __name__ == "__main__":
    unittest.main()
