#!/usr/bin/env python3
"""Refresh the low-frequency, redistributable USD/JPY reference anchor."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from update_rates import UTC, fetch_reference_rate, iso_utc, write_atomic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/usdjpy-reference.json"))
    args = parser.parse_args()

    rate, rate_date, source = fetch_reference_rate()
    document = {
        "schema": 1,
        "checked_at": iso_utc(datetime.now(UTC)),
        "base": "USD",
        "quote": "JPY",
        "rate": float(rate),
        "rate_date": rate_date,
        "source": source,
    }
    write_atomic(args.output, document)
    print(f"Updated {args.output}: USD/JPY={rate} reference_date={rate_date} source={source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
