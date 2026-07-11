#!/usr/bin/env python3
"""Generate the public MochiFX USD/JPY game quote.

The reference anchor is an openly redistributable daily USD/JPY rate. Bid, ask
and the five-minute movement are explicitly synthetic and intended only for the
MochiFX virtual-currency simulator.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


UTC = timezone.utc
PAIR = "USDJPY"
SPREAD = Decimal("0.010")
HALF_SPREAD = SPREAD / 2
PRICE_QUANTUM = Decimal("0.001")

FRANKFURTER_URL = "https://api.frankfurter.dev/v2/rate/USD/JPY?providers=ECB"
FALLBACK_URLS = (
    "https://latest.currency-api.pages.dev/v1/currencies/usd.json",
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
)


def iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_fx_market_open(value: datetime) -> bool:
    """Approximate the global FX week: Sunday 22:00 through Friday 22:00 UTC."""
    value = value.astimezone(UTC)
    weekday = value.weekday()  # Monday=0, Sunday=6

    if weekday <= 3:
        return True
    if weekday == 4:
        return value.hour < 22
    if weekday == 5:
        return False
    return value.hour >= 22


def effective_five_minute_bucket(now: datetime) -> int:
    """Return the active five-minute bucket, frozen at the last open-market tick."""
    cursor = now.astimezone(UTC).replace(second=0, microsecond=0)
    cursor -= timedelta(minutes=cursor.minute % 5)

    while not is_fx_market_open(cursor):
        cursor -= timedelta(minutes=5)

    return int(cursor.timestamp()) // 300


def request_json(url: str, attempts: int = 3) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MochiFX-Rates/1.0 (+https://github.com/superme1on/mochimochi-fx-rates)",
        },
    )

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status} from {url}")
                return json.load(response)
        except (OSError, RuntimeError, json.JSONDecodeError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Could not load {url}: {last_error}")


def parse_frankfurter(payload: Any) -> tuple[Decimal, str]:
    rate = Decimal(str(payload["rate"]))
    rate_date = str(payload["date"])
    return rate, rate_date


def parse_currency_api(payload: Any) -> tuple[Decimal, str]:
    rate = Decimal(str(payload["usd"]["jpy"]))
    rate_date = str(payload["date"])
    return rate, rate_date


def validate_reference_rate(rate: Decimal) -> None:
    if not Decimal("50") <= rate <= Decimal("300"):
        raise ValueError(f"USD/JPY reference rate is outside the safety range: {rate}")


def fetch_reference_rate() -> tuple[Decimal, str, str]:
    errors: list[str] = []

    try:
        rate, rate_date = parse_frankfurter(request_json(FRANKFURTER_URL))
        validate_reference_rate(rate)
        return rate, rate_date, "European Central Bank via Frankfurter"
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        errors.append(f"Frankfurter: {exc}")

    for url in FALLBACK_URLS:
        try:
            rate, rate_date = parse_currency_api(request_json(url))
            validate_reference_rate(rate)
            return rate, rate_date, "fawazahmed0 currency-api fallback"
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            errors.append(f"{url}: {exc}")

    raise RuntimeError("All reference-rate providers failed: " + " | ".join(errors))


def load_reference_file(path: Path) -> tuple[Decimal, str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rate = Decimal(str(payload["rate"]))
    rate_date = str(payload["rate_date"])
    source = str(payload["source"])
    validate_reference_rate(rate)
    return rate, rate_date, source


def simulated_mid(reference_rate: Decimal, bucket: int) -> Decimal:
    """Generate a deterministic, bounded five-minute movement around the anchor."""
    n = bucket % 100_000
    offset = (
        0.025 * math.sin((2.0 * math.pi * n) / 97.0)
        + 0.015 * math.sin((2.0 * math.pi * n) / 37.0)
        + 0.008 * math.sin((2.0 * math.pi * n) / 13.0)
    )
    return (reference_rate + Decimal(str(offset))).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def build_document(reference_rate: Decimal, rate_date: str, source: str, now: datetime) -> dict[str, Any]:
    validate_reference_rate(reference_rate)

    bucket = effective_five_minute_bucket(now)
    tick_time = datetime.fromtimestamp(bucket * 300, tz=UTC)
    mid = simulated_mid(reference_rate, bucket)
    bid = (mid - HALF_SPREAD).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)
    ask = (mid + HALF_SPREAD).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)

    if bid > ask or (ask - bid) != SPREAD:
        raise AssertionError("Generated quote failed bid/ask validation")

    return {
        "schema": 2,
        "generated_at": iso_utc(now),
        "game_currency": "mochi",
        "feed": {
            "source": source,
            "source_rate_date": rate_date,
            "source_rate": float(reference_rate),
            "mode": "reference_anchored_sim",
            "quote_kind": "indicative_game_quote",
            "market_status": "open" if is_fx_market_open(now) else "closed",
            "refresh_seconds": 300,
            "sequence": bucket,
        },
        "pairs": {
            PAIR: {
                "bid": float(bid),
                "ask": float(ask),
                "mid": float(mid),
                "spread": float(SPREAD),
                "ts": iso_utc(tick_time),
            }
        },
    }


def write_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary_path, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/rates.json"))
    parser.add_argument(
        "--reference",
        type=Path,
        help="Read the daily reference anchor from this JSON file instead of calling a provider.",
    )
    args = parser.parse_args()

    now = datetime.now(UTC)
    if args.reference is None:
        reference_rate, rate_date, source = fetch_reference_rate()
    else:
        reference_rate, rate_date, source = load_reference_file(args.reference)
    document = build_document(reference_rate, rate_date, source, now)
    write_atomic(args.output, document)

    quote = document["pairs"][PAIR]
    feed = document["feed"]
    print(
        f"Generated {args.output}: {PAIR} bid={quote['bid']:.3f} "
        f"ask={quote['ask']:.3f} status={feed['market_status']} "
        f"source_date={feed['source_rate_date']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
