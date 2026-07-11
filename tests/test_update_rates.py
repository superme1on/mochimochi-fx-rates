import sys
import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import update_rates


UTC = timezone.utc


class UpdateRatesTests(unittest.TestCase):
    def test_market_week_boundaries(self):
        self.assertFalse(update_rates.is_fx_market_open(datetime(2026, 7, 12, 21, 59, tzinfo=UTC)))
        self.assertTrue(update_rates.is_fx_market_open(datetime(2026, 7, 12, 22, 0, tzinfo=UTC)))
        self.assertTrue(update_rates.is_fx_market_open(datetime(2026, 7, 17, 21, 59, tzinfo=UTC)))
        self.assertFalse(update_rates.is_fx_market_open(datetime(2026, 7, 17, 22, 0, tzinfo=UTC)))

    def test_closed_market_uses_last_open_bucket(self):
        saturday = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)
        friday_close_tick = datetime(2026, 7, 10, 21, 55, tzinfo=UTC)
        self.assertEqual(
            update_rates.effective_five_minute_bucket(saturday),
            int(friday_close_tick.timestamp()) // 300,
        )

    def test_quote_has_valid_spread_and_metadata(self):
        now = datetime(2026, 7, 13, 10, 2, 34, tzinfo=UTC)
        document = update_rates.build_document(
            Decimal("161.87"),
            "2026-07-10",
            "test provider",
            now,
        )

        quote = document["pairs"]["USDJPY"]
        self.assertLess(quote["bid"], quote["ask"])
        self.assertAlmostEqual(quote["ask"] - quote["bid"], 0.010, places=9)
        self.assertEqual(document["schema"], 2)
        self.assertEqual(document["feed"]["mode"], "reference_anchored_sim")
        self.assertEqual(document["feed"]["market_status"], "open")

    def test_provider_payload_parsers(self):
        self.assertEqual(
            update_rates.parse_frankfurter({"date": "2026-07-10", "rate": 161.87}),
            (Decimal("161.87"), "2026-07-10"),
        )
        self.assertEqual(
            update_rates.parse_currency_api({"date": "2026-07-10", "usd": {"jpy": 161.4}}),
            (Decimal("161.4"), "2026-07-10"),
        )

    def test_load_reference_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.json"
            path.write_text(
                json.dumps(
                    {
                        "rate": 161.87,
                        "rate_date": "2026-07-10",
                        "source": "test source",
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                update_rates.load_reference_file(path),
                (Decimal("161.87"), "2026-07-10", "test source"),
            )


if __name__ == "__main__":
    unittest.main()
