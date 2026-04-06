#!/usr/bin/env python3
"""
Quick sanity check for the transport.opendata.ch SBB API.
Tests that each planned origin resolves and returns plausible travel times.

Usage:
    python3 test_sbb.py
"""

import sys
import time
try:
    import requests
except ImportError:
    print("Missing dependency. Run:  pip3 install requests")
    sys.exit(1)

DELAY = 2.0  # match scraper's SBB_DELAY to avoid rate-limiting

SBB_API = "https://transport.opendata.ch/v1"

# (origin, destination, min_minutes, max_minutes)
# Times are rough — just checking the API returns something plausible
TESTS = [
    ("Basel SBB",   "Sargans",        60,  180),
    ("Basel SBB",   "Montreux",       90,  240),
    ("Zürich HB",   "Sargans",        20,   90),
    ("Zürich HB",   "Montreux",       90,  240),
    ("Bern",        "Sargans",        60,  180),
    ("Bern",        "Montreux",       40,  120),
    ("Lausanne",    "Montreux",        5,   40),
    ("Lausanne",    "Sargans",        90,  240),
    ("Genève",      "Montreux",       40,  100),
    ("Genève",      "Sargans",       120,  300),
    ("Luzern",      "Sargans",        20,   90),
    ("Luzern",      "Montreux",       90,  240),
    ("St. Gallen",  "Sargans",        20,   90),
    ("St. Gallen",  "Montreux",      120,  300),
    ("Winterthur",  "Sargans",        30,  120),
    ("Winterthur",  "Montreux",       90,  240),
    ("Biel/Bienne", "Montreux",       40,  120),
    ("Biel/Bienne", "Sargans",        60,  180),
    ("Lugano",      "Sargans",        90,  240),
    ("Lugano",      "Montreux",       90,  300),
]

def get_travel_time(origin, destination):
    """Returns minutes (int) or None. Raises on daily quota error."""
    r = requests.get(
        f"{SBB_API}/connections",
        params={"from": origin, "to": destination, "limit": 1},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    errors = body.get("errors", [])
    if errors:
        msg = (errors[0].get("message") or "").lower()
        if "too many requests" in msg or "rate limit" in msg:
            return None, f"DAILY QUOTA EXCEEDED: {errors[0]['message']}"
        return None, f"API error: {errors[0].get('message')}"
    if r.status_code == 429:
        return None, "rate-limited (429)"
    conns = body.get("connections", [])
    if not conns:
        return None, "no connection found"
    c = conns[0]
    dep = c["from"]["departureTimestamp"]
    arr = c["to"]["arrivalTimestamp"]
    if not (dep and arr):
        return None, "missing timestamps"
    return int((arr - dep) / 60), None

def main():
    passed = 0
    failed = 0

    print(f"Testing SBB API ({SBB_API})\n")
    print(f"{'Origin':<16} {'→ Destination':<16} {'Minutes':>8}  {'Result'}")
    print("-" * 60)

    for i, (origin, dest, lo, hi) in enumerate(TESTS):
        if i > 0:
            time.sleep(DELAY)
        minutes, err = get_travel_time(origin, dest)
        if err and "DAILY QUOTA" in err:
            print(f"\n!! {err}")
            print("   Re-run tomorrow after midnight Swiss time.")
            sys.exit(1)
        elif err:
            status = f"FAIL  ({err})"
            failed += 1
        elif not (lo <= minutes <= hi):
            status = f"FAIL  ({minutes} min, expected {lo}–{hi})"
            failed += 1
        else:
            status = f"ok    ({minutes} min)"
            passed += 1
        print(f"{origin:<16} {'→ ' + dest:<16} {str(minutes or '—'):>8}  {status}")

    print("-" * 60)
    print(f"\n{passed} passed, {failed} failed\n")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
