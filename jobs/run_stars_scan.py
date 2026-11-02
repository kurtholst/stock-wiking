"""Scheduled Stars scan.

Runs the same scan as the "Stars" tab and persists it to data/stars_latest.json,
where the Stars and Alpha-signals tabs pick it up. With --deep it runs the
multi-quarter deep alpha analysis instead (data/alpha_deep_latest.json).

Usage (from the repo root):
    .venv/bin/python jobs/run_stars_scan.py [--period-days 90]
    .venv/bin/python jobs/run_stars_scan.py --deep [--quarters 8]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env the same way app.py does (EPO_OPS_KEY, GEMINI_API_KEY, ...)
_env_file = ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from server.alpha import run_deep_analysis  # noqa: E402
from server.patents import run_stars_scan  # noqa: E402
from server.runner import scan_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Stars patent scan")
    parser.add_argument("--period-days", type=int, default=90)
    parser.add_argument("--deep", action="store_true", help="Run the deep alpha analysis")
    parser.add_argument("--quarters", type=int, default=8)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Wait for any manual run from the app to finish instead of overlapping it
    with scan_lock(blocking=True):
        if args.deep:
            deep = run_deep_analysis(
                args.quarters, trigger="scheduled",
                progress=lambda i, n, msg: logging.info("[%d/%d] %s", i + 1, n, msg),
            )
            logging.info(
                "Deep analysis done in %ds: top %s (%.0f), %d warnings",
                deep.duration_s, deep.companies[0].name, deep.companies[0].alpha_score, len(deep.warnings),
            )
            return 0
        result = run_stars_scan(args.period_days, trigger="scheduled")
    flagged = sum(1 for c in result.companies if c.area_shift and c.area_shift.flagged)
    logging.info(
        "Stars scan done at %s: %d companies, %d patents, %d area shifts flagged",
        result.run_at, len(result.companies), result.total_patents, flagged,
    )
    return 0 if result.companies else 1


if __name__ == "__main__":
    sys.exit(main())
