"""MagnetismBar must not reach for state it does not own.

The "Crawler identity forgery detected" panel was pasted into MagnetismBar, a
presentational component whose only prop is `score`. It referenced `overview`,
which is state in the AICrawlers component further down the file, so every
render threw `ReferenceError: overview is not defined` and white-screened the
whole page.

It stayed hidden because MagnetismBar renders one row per entry of
`Top Verified Crawled Pages`, which needs verified AI-crawler page data. An
install with none never rendered it. It surfaced only once crawler verification
started working, which was itself blocked by a separate importer bug.

There is no JavaScript test runner in this repository and adding one for this
would be a larger change than the fix, so this reads the source, in the same way
test_cli_import_parity.py asserts the CLI importer does not build rows itself.
"""

import re
import sys
import unittest
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

AICRAWLERS = BACKEND.parent / "frontend" / "src" / "pages" / "AICrawlers.jsx"


def _component_body(source: str, name: str) -> str:
    """Text from `function <name>(` up to the next top-level function or export."""
    start = re.search(rf"^function {name}\(", source, re.M)
    assert start, f"{name} not found in AICrawlers.jsx"
    rest = source[start.end():]
    nxt = re.search(r"^(function |export default )", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


class AICrawlersScopeTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(AICRAWLERS.is_file(), f"missing {AICRAWLERS}")
        self.source = AICRAWLERS.read_text(encoding="utf-8")

    def test_magnetism_bar_does_not_reference_overview(self):
        body = _component_body(self.source, "MagnetismBar")
        self.assertNotIn(
            "overview", body,
            "MagnetismBar references `overview`, which is state in the AICrawlers "
            "component. That throws ReferenceError on every render and blanks the page.",
        )

    def test_magnetism_bar_uses_only_its_own_props(self):
        body = _component_body(self.source, "MagnetismBar")
        for name in ("crawlers", "pages", "loading", "days", "setDays"):
            self.assertNotIn(
                f"{name}?" , body,
                f"MagnetismBar reaches for `{name}`, which it does not receive as a prop.",
            )

    def test_the_forgery_panel_still_exists_somewhere(self):
        # The fix moves the panel; it must not quietly delete the feature.
        self.assertIn("Crawler identity forgery detected", self.source)
        self.assertIn("crawler_verification", self.source)


if __name__ == "__main__":
    unittest.main()
