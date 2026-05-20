"""
Pulls monthly visit estimates from the Semrush Traffic Analytics API for a list
of domains and writes results to a CSV.

IMPORTANT — API scope:
  Semrush Traffic Analytics operates at the domain or subdomain level. If you
  pass a path like "nytimes.com/crosswords/", Semrush strips the path and
  returns data for "nytimes.com" as a whole. Subdomain targets like
  "games.usatoday.com" work correctly.

Usage:
  1. Set SEMRUSH_API_KEY below (or export it as an env var).
  2. Adjust TARGETS, START_YEAR_MONTH, and COUNTRY if needed.
  3. Run: python3 semrush_monthly_visits.py
     Output is written to semrush_monthly_visits.csv.

API units:
  Each monthly request is batched — all targets are sent in a single call per
  month, so total calls = number of months. Units are charged even when a
  domain has no data for that month.
"""

import csv
import os
import time
from datetime import date, datetime

import requests

# ── Configuration ────────────────────────────────────────────────────────────

SEMRUSH_API_KEY = os.getenv("SEMRUSH_API_KEY", "YOUR_API_KEY_HERE")

# Domains (or subdomains). Paths after the domain are not supported by the API.
TARGETS = [
    "nytimes.com",       # full domain; /crosswords/ path not resolvable via API
    "linkedin.com",      # full domain; /games/ path not resolvable via API
    "theatlantic.com",   # full domain; /games/ path not resolvable via API
    "games.usatoday.com",
]

# Fetch from this month onward (YYYY, MM)
START_YEAR_MONTH = (2019, 1)

# "us" for United States, "world" for global
COUNTRY = "us"

OUTPUT_FILE = "semrush_monthly_visits.csv"

SEMRUSH_TA_URL = "https://api.semrush.com/analytics/ta/api/v3/summary"

# ── Helpers ───────────────────────────────────────────────────────────────────

def month_range(start_ym: tuple[int, int], end_ym: tuple[int, int]):
    """Yield (year, month) tuples from start to end inclusive."""
    y, m = start_ym
    ey, em = end_ym
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def fetch_month(year: int, month: int) -> dict[str, int | None]:
    """
    Fetch visit estimates for all TARGETS for a single month.
    Returns {target: visits} — visits is None when Semrush has no data.
    """
    display_date = f"{year}{month:02d}01"
    params = {
        "targets": ",".join(TARGETS),
        "display_date": display_date,
        "country": COUNTRY,
        "export_columns": "target,visits",
        "key": SEMRUSH_API_KEY,
    }
    resp = requests.get(SEMRUSH_TA_URL, params=params, timeout=30)

    if resp.status_code == 400:
        # Semrush returns 400 when date is out of range or key has no TA access
        return {t: None for t in TARGETS}

    resp.raise_for_status()

    result = {t: None for t in TARGETS}
    for line in resp.text.strip().splitlines():
        parts = line.split(";")
        if len(parts) < 2:
            continue
        target, raw_visits = parts[0], parts[1]
        try:
            result[target] = int(raw_visits)
        except ValueError:
            result[target] = None

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if SEMRUSH_API_KEY == "YOUR_API_KEY_HERE":
        raise SystemExit(
            "Error: set your Semrush API key in SEMRUSH_API_KEY or via the "
            "SEMRUSH_API_KEY environment variable."
        )

    today = date.today()
    end_ym = (today.year, today.month)

    months = list(month_range(START_YEAR_MONTH, end_ym))
    print(f"Fetching {len(months)} months × {len(TARGETS)} targets → {OUTPUT_FILE}")
    print(f"Country: {COUNTRY} | Targets: {', '.join(TARGETS)}\n")

    rows = []
    for i, (y, m) in enumerate(months, 1):
        label = f"{y}-{m:02d}"
        print(f"  [{i:3d}/{len(months)}] {label} ... ", end="", flush=True)
        try:
            visits_by_target = fetch_month(y, m)
            for target, visits in visits_by_target.items():
                rows.append({"year_month": label, "target": target, "visits": visits})
            counts = [str(v) if v is not None else "—" for v in visits_by_target.values()]
            print(" | ".join(counts))
        except requests.HTTPError as exc:
            print(f"HTTP {exc.response.status_code} — skipping")
        except Exception as exc:
            print(f"Error: {exc} — skipping")

        # Be polite to the API; Semrush rate-limits at ~10 req/s
        if i < len(months):
            time.sleep(0.15)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["year_month", "target", "visits"])
        writer.writeheader()
        writer.writerows(rows)

    non_null = sum(1 for r in rows if r["visits"] is not None)
    print(f"\nWrote {len(rows)} rows ({non_null} with data) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
