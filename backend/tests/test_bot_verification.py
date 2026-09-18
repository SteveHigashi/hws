import sys
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.bot import classify_bot  # noqa: E402


class BotVerificationTests(unittest.TestCase):
    def test_forged_googlebot_is_loudly_classified(self):
        result = classify_bot("Mozilla/5.0 (compatible; Googlebot/2.1)", "203.0.113.9")
        self.assertEqual(result["name"], "Googlebot")
        self.assertEqual(result["verification_state"], "forged")
        self.assertEqual(result["verification_method"], "prefix_mismatch")

    def test_googlebot_in_published_prefix_is_verified(self):
        result = classify_bot("Googlebot/2.1", "192.178.4.1")
        self.assertEqual(result["verification_state"], "verified")
        self.assertEqual(result["verification_method"], "published_prefix")

    def test_fcrdns_can_verify_a_fresh_google_address_outside_bundled_prefixes(self):
        result = classify_bot(
            "Googlebot/2.1",
            "203.0.113.11",
            fcrdns_lookup=lambda _ip: "crawl-203-0-113-11.googlebot.com",
        )
        self.assertEqual(result["verification_state"], "verified")
        self.assertEqual(result["verification_method"], "fcrdns")

    def test_claim_without_address_is_never_verified(self):
        result = classify_bot("Googlebot/2.1")
        self.assertEqual(result["verification_state"], "unverified")

    def test_fcrdns_fallback_for_family_without_prefixes(self):
        result = classify_bot(
            "YandexBot/3.0",
            "203.0.113.10",
            fcrdns_lookup=lambda _ip: "crawler.yandex.ru",
        )
        self.assertEqual(result["verification_state"], "verified")
        self.assertEqual(result["verification_method"], "fcrdns")


if __name__ == "__main__":
    unittest.main()
