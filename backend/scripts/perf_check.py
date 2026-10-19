"""Response-time check against a running server (RD NFR-3.2.1: 95% of requests < 2 s).

    python scripts/perf_check.py http://127.0.0.1:5000 --requests 200

Only hits public, read-only endpoints, so it's safe to run against the demo server.
"""

import argparse
import statistics
import sys
import time
import urllib.request

ENDPOINTS = ["/api/v1/health", "/api/v1/resources", "/api/v1/emergency/config"]
TARGET_SECONDS = 2.0


def timed_get(url: str) -> float:
    start = time.perf_counter()
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 (operator-supplied URL)
        response.read()
    return time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url")
    parser.add_argument("--requests", type=int, default=100, help="Requests per endpoint.")
    args = parser.parse_args()

    failed = False
    for path in ENDPOINTS:
        samples = sorted(timed_get(args.base_url.rstrip("/") + path) for _ in range(args.requests))
        p95 = samples[int(len(samples) * 0.95) - 1]
        ok = p95 < TARGET_SECONDS
        failed |= not ok
        median_ms = statistics.median(samples) * 1000
        print(
            f"{'PASS' if ok else 'FAIL'} {path}: median {median_ms:.0f} ms, "
            f"p95 {p95 * 1000:.0f} ms over {len(samples)} requests"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
