"""Send an ntfy alert when a scheduled job fails (systemd OnFailure= hook).

Usage: .venv/bin/python jobs/notify_failure.py <unit-name>
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_env_file = ROOT / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from server import alerts  # noqa: E402


def main() -> int:
    unit = sys.argv[1] if len(sys.argv) > 1 else "scheduled job"
    if not alerts.is_configured():
        print("NTFY_TOPIC not set - cannot send failure alert", file=sys.stderr)
        return 1
    alerts.send(
        f"Stock Wiking: {unit} failed",
        f"The scheduled run of {unit} did not finish, so no daily summary was sent.\n"
        f"Check: journalctl --user -u {unit}",
        "critical",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
