"""Every setting that sends data out is documented where an operator will look.

This test exists because the documentation fell behind the code twice in one day.
The README was written when HWS had two outbound paths, research sharing was added
afterwards, and the README went on saying "no research data collection in HWS.
None exists in the code" while the code contained exactly that. .env.example
documented EXTERNAL_GEO and not RESEARCH_SHARING.

A privacy claim that is false is worse than no claim, so the claims are tested.
"""
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from config import Settings  # noqa: E402

# Settings that cause data to leave the operator's server. Add one here and the
# test will tell you which documents still need to mention it.
EGRESS_SETTINGS = ("external_geo", "research_sharing", "live_key")


class EgressSettingsAreDocumented(unittest.TestCase):
    def test_every_egress_setting_exists(self):
        s = Settings(_env_file=None)
        for name in EGRESS_SETTINGS:
            self.assertTrue(hasattr(s, name), "%s is named here but not in Settings" % name)

    def test_env_example_documents_each_one(self):
        text = (ROOT / ".env.example").read_text()
        for name in EGRESS_SETTINGS:
            self.assertIn(
                name.upper(), text,
                "%s sends data out and is not documented in .env.example" % name.upper(),
            )

    def test_readme_documents_each_one(self):
        text = (ROOT / "README.md").read_text()
        for name in EGRESS_SETTINGS:
            self.assertIn(
                name.upper(), text,
                "%s sends data out and is not mentioned in the README" % name.upper(),
            )

    def test_readme_does_not_deny_what_the_code_does(self):
        """The specific false sentence, and the shape of it."""
        text = (ROOT / "README.md").read_text().lower()
        for denial in (
            "no research data collection",
            "none exists in the code",
        ):
            self.assertNotIn(
                denial, text,
                "the README denies something the code does: %r" % denial,
            )

    def test_the_egress_table_lists_three_things(self):
        """The README's 'What leaves your server' table must cover all three."""
        text = (ROOT / "README.md").read_text()
        # Split on a horizontal rule on its own line: the table's own
        # |---|---|---| separator contains "---" and ended the slice early.
        table = text.split("What leaves your server", 1)[1].split("\n---\n", 1)[0]
        for marker in ("LIVE_KEY", "EXTERNAL_GEO", "RESEARCH_SHARING"):
            self.assertIn(marker, table,
                          "the egress table does not mention %r" % marker)


if __name__ == "__main__":
    unittest.main()
