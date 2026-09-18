import random
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.walk_detection import (  # noqa: E402
    LogRow,
    analyze_walk,
    asset_fetch_signal,
    detect_order,
    detect_shape,
    distributed_walk_signal,
    engagement_absence_signal,
    per_address_rate,
    records_taken_rows,
)


START = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


def row(index, slug, identity=None, size=50_000, path=None, referrer=None, **kwargs):
    return LogRow(
        timestamp=START + timedelta(seconds=index),
        identity=identity or f"id-{index}",
        method=kwargs.get("method", "GET"),
        path=path or f"/catalogue/{slug}",
        status=kwargs.get("status", 200),
        response_bytes=size,
        content_type=kwargs.get("content_type"),
        referrer=referrer,
        user_agent=kwargs.get("user_agent", "Mozilla/5.0"),
        bot_name=kwargs.get("bot_name"),
        bot_verification=kwargs.get("bot_verification"),
    )


class WalkDetectionTests(unittest.TestCase):
    def test_shuffled_walk_fires_shape_without_order(self):
        slugs = ["a", "z", "b", "y", "c", "x", "d", "w", "e", "v", "f", "u", "g", "t"]
        rows = [row(i, slug) for i, slug in enumerate(slugs)]
        result = analyze_walk(rows)
        self.assertIn("shape", result.triggers)
        self.assertNotIn("order", result.triggers)
        self.assertEqual(result.verdict, "walk_detected")

    def test_single_source_sorted_walk_fires_order_independently(self):
        rows = [row(i, f"item-{i:02d}", identity="one-source") for i in range(14)]
        shape = detect_shape(rows)
        order = detect_order(rows)
        self.assertFalse(shape["fired"])
        self.assertTrue(order["fired"])

    def test_asset_fetch_ratio_distinguishes_rendering_clients(self):
        rows = []
        for i in range(10):
            identity = f"browser-{i}"
            rows.extend([
                row(i * 3, f"item-{i}", identity=identity),
                row(i * 3 + 1, "", identity=identity, path=f"/assets/app-{i}.js", size=8000),
                row(i * 3 + 2, "", identity=identity, path=f"/images/logo-{i}.png", size=4000),
            ])
        signal = asset_fetch_signal(rows)
        self.assertEqual(signal["content_responses"], 10)
        self.assertEqual(signal["assetless_identity_share"], 0)

    def test_asset_type_can_be_inferred_from_content_type(self):
        rows = [row(i, f"item-{i}", identity=f"browser-{i}") for i in range(3)]
        rows.append(row(
            4, "", identity="browser-0", path="/resource", size=4000,
            content_type="text/css; charset=utf-8",
        ))
        signal = asset_fetch_signal(rows)
        self.assertEqual(signal["asset_responses"], 1)

    def test_gated_200_is_not_counted_as_record_taken(self):
        rows = [row(i, f"item-{i}", size=50_000) for i in range(3)]
        rows.append(row(4, "item-gated", size=450, status=200))
        taken = records_taken_rows(rows)
        self.assertEqual(len(taken), 3)
        self.assertNotIn("/catalogue/item-gated", {item.path for item in taken})

    def test_per_address_rate_calls_out_rotating_pool_blind_spot(self):
        rows = [row(i, f"item-{i}") for i in range(20)]
        signal = per_address_rate(rows)
        self.assertEqual(signal["median"], 1)
        self.assertEqual(signal["singleton_share"], 1)
        self.assertTrue(signal["blind_spot"])

    def test_distributed_queue_and_missing_referers(self):
        rows = [row(i, f"alpha-{i:02d}", identity=f"pool-{i}") for i in range(14)]
        signal = distributed_walk_signal(rows)
        self.assertEqual(signal["referer_absence_ratio"], 1)
        self.assertEqual(signal["shared_queue_ratio"], 1)
        self.assertEqual(signal["cross_address_pairs"], 13)

    def test_scroll_absence_is_only_corroboration(self):
        rows = [row(i, f"item-{i}", identity="reader") for i in range(3)]
        absence = engagement_absence_signal(total_sessions=10, engaged_sessions=0)
        result = analyze_walk(rows, engagement_absence_ratio=absence)
        self.assertEqual(absence, 1)
        self.assertNotIn("shape", result.triggers)
        self.assertNotIn("order", result.triggers)
        self.assertNotEqual(result.verdict, "walk_detected")

    def test_verified_crawler_does_not_trigger_shape(self):
        rows = [
            row(
                i, f"item-{i}", bot_name="Googlebot", bot_verification="verified",
                user_agent="Googlebot/2.1",
            )
            for i in range(14)
        ]
        self.assertFalse(detect_shape(rows)["fired"])


if __name__ == "__main__":
    unittest.main()
