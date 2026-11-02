"""Phone alerts for critical alpha signals via ntfy (https://ntfy.sh).

Evaluated after every Stars scan and deep analysis (manual or scheduled).
Each signal is sent once: sent keys are remembered in data/alerts_sent.json
and expire after _RESEND_AFTER_DAYS, so a persisting signal can re-alert later.

Config (.env):
    NTFY_TOPIC      required - long random topic name (acts as the password)
    NTFY_SERVER     optional - default https://ntfy.sh
    ALERT_BASE_URL  optional - link target, default https://familienholst.duckdns.org/stock/
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import threading
from pathlib import Path
from urllib.parse import quote

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "alerts_sent.json"
_RESEND_AFTER_DAYS = 60
_MAX_CRITICAL_PER_RUN = 5

# --- Rules -----------------------------------------------------------------
# Critical (urgent push): a strong company is moving into a technology area it has not filed in before,
# or the deep analysis finds a high-conviction move the market has not priced in.
CRIT_STARS_MIN = 4
CRIT_DEEP_SCORE_MIN = 60
CRIT_DEEP_CONVICTION_MIN = 4
# Notable (normal push): accelerating shifts and cross-company themes.
NOTABLE_ACCEL_SCORE_MIN = 40

_lock = threading.Lock()


class Alert(BaseModel):
    key: str
    level: str          # critical | notable | digest
    title: str
    message: str
    ticker: str | None = None


# ---------------------------------------------------------------------------
# Rules -> alerts
# ---------------------------------------------------------------------------

def stars_alerts(scan) -> list[Alert]:
    alerts: list[Alert] = []
    by_code: dict[str, list[str]] = {}
    for c in scan.companies:
        s = c.area_shift
        if not s or not s.data_complete:
            continue
        for code in s.new_ipc:
            by_code.setdefault(code, []).append(c.name)
        if (c.stars or 0) >= CRIT_STARS_MIN and s.flagged and s.new_ipc:
            new = ", ".join(s.new_ipc)
            alerts.append(Alert(
                key=f"stars:{c.ticker}:{','.join(sorted(s.new_ipc))}",
                level="critical",
                ticker=c.ticker,
                title=f"{c.name}: new patent area ({c.stars}★)",
                message=(
                    f"New IPC classes: {new}. Tech shift {_pct(s.ipc_shift)}, office shift {_pct(s.office_shift)} "
                    f"({s.recent_count} recent vs {s.baseline_count} in prior 12m)."
                    + (f" Signal {c.ai_signal}." if c.ai_signal else "")
                    + (f" 1D {c.stock_change_pct:+.2f}%." if c.stock_change_pct is not None else "")
                ),
            ))
    for code, names in by_code.items():
        if len(names) >= 2:
            alerts.append(Alert(
                key=f"theme:{code}:{','.join(sorted(names))}",
                level="notable",
                title=f"Theme: {len(names)} companies moving into {code}",
                message=", ".join(names),
            ))
    return alerts


def deep_alerts(deep) -> list[Alert]:
    alerts: list[Alert] = []
    for c in deep.companies:
        t = c.thesis
        # conviction on a NOISE thesis means "confident it's noise" - never alert on that
        if (t and t.move_type != "NOISE" and c.alpha_score >= CRIT_DEEP_SCORE_MIN
                and t.conviction >= CRIT_DEEP_CONVICTION_MIN and t.priced_in == "LOW"):
            alerts.append(Alert(
                key=f"deep:{c.ticker}:{t.move_type}",
                level="critical",
                ticker=c.ticker,
                title=f"{c.name}: {t.move_type.replace('_', ' ').lower()} - conviction {t.conviction}/5",
                message=(
                    f"Alpha Score {c.alpha_score:.0f}, not priced in. {_first_sentence(t.hypothesis)} "
                    f"6M {_pct(c.return_6m, signed=True)}."
                ),
            ))
        elif c.shift_trend == "ACCELERATING" and c.alpha_score >= NOTABLE_ACCEL_SCORE_MIN:
            alerts.append(Alert(
                key=f"accel:{c.ticker}",
                level="notable",
                ticker=c.ticker,
                title=f"{c.name}: patent shift accelerating",
                message=(
                    f"Alpha Score {c.alpha_score:.0f}, mix shift {_pct(c.recent_shift)}, "
                    f"velocity {c.velocity_ratio or '-'}x"
                    + (f", new classes {', '.join(e.code for e in c.emerging)}" if c.emerging else "") + "."
                ),
            ))
    for th in deep.themes:
        alerts.append(Alert(
            key=f"theme:{th.code}:{','.join(sorted(th.companies))}",
            level="notable",
            title=f"Theme: {len(th.companies)} companies moving into {th.code}",
            message=", ".join(th.companies),
        ))
    if deep.trigger == "scheduled":
        top = ", ".join(f"{c.name} {c.alpha_score:.0f}" for c in deep.companies[:3])
        alerts.append(Alert(
            key=f"digest:{deep.run_at}",
            level="digest",
            title="Weekly alpha digest",
            message=f"Top: {top}. {_first_sentence(deep.memo)}",
        ))
    return alerts


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def _pct(v, signed: bool = False) -> str:
    if v is None:
        return "-"
    return f"{v * 100:+.0f}%" if signed else f"{v * 100:.0f}%"


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    end = text.find(". ")
    return text if end == -1 else text[: end + 1]


def is_configured() -> bool:
    return bool(os.environ.get("NTFY_TOPIC"))


def _link(ticker: str | None) -> str:
    base = os.environ.get("ALERT_BASE_URL", "https://familienholst.duckdns.org/stock/")
    return f"{base}?tab=alpha" + (f"&focus={quote(ticker)}" if ticker else "")


_PRIORITY = {"critical": 5, "notable": 3, "digest": 2, "test": 3}
_TAGS = {"critical": ["rotating_light"], "notable": ["chart_with_upwards_trend"], "digest": ["memo"], "test": ["white_check_mark"]}


def send(title: str, message: str, level: str, ticker: str | None = None) -> None:
    topic = os.environ["NTFY_TOPIC"]
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    resp = httpx.post(
        server,
        json={
            "topic": topic,
            "title": title,
            "message": message,
            "priority": _PRIORITY.get(level, 3),
            "tags": _TAGS.get(level, []),
            "click": _link(ticker),
            "actions": [{"action": "view", "label": "Open Alpha-signals", "url": _link(ticker)}],
        },
        timeout=15,
    )
    resp.raise_for_status()


def _load_state() -> dict[str, dict]:
    try:
        return json.loads(_STATE_FILE.read_text()) if _STATE_FILE.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, dict]) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(_STATE_FILE)


def dispatch(alerts: list[Alert]) -> list[Alert]:
    """Send alerts not sent before. Returns the ones sent. Never raises."""
    if not alerts or not is_configured():
        return []
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = (now - datetime.timedelta(days=_RESEND_AFTER_DAYS)).isoformat()
    sent: list[Alert] = []
    with _lock:
        state = {k: v for k, v in _load_state().items() if v.get("sent_at", "") >= cutoff}
        fresh = [a for a in alerts if a.key not in state]
        critical = [a for a in fresh if a.level == "critical"][:_MAX_CRITICAL_PER_RUN]
        notable = [a for a in fresh if a.level == "notable"]
        digest = [a for a in fresh if a.level == "digest"]

        batches: list[tuple[list[Alert], str, str, str | None]] = [
            ([a], a.title, a.message, a.ticker) for a in critical + digest
        ]
        if len(notable) == 1:
            batches.append((notable, notable[0].title, notable[0].message, notable[0].ticker))
        elif notable:
            batches.append((notable, f"{len(notable)} notable alpha signals",
                            "\n".join(f"• {a.title}: {a.message}" for a in notable), None))

        for group, title, message, ticker in batches:
            try:
                send(title, message, group[0].level, ticker)
            except Exception:
                logger.exception("ntfy send failed for %s", title)
                continue
            for a in group:
                state[a.key] = {"sent_at": now.isoformat(timespec="seconds"), "level": a.level,
                                "title": a.title, "message": a.message}
                sent.append(a)
        _save_state(state)
    if sent:
        logger.info("Sent %d alpha alerts", len(sent))
    return sent


def notify_stars(scan) -> list[Alert]:
    try:
        return dispatch(stars_alerts(scan))
    except Exception:
        logger.exception("Stars alert evaluation failed")
        return []


def notify_deep(deep) -> list[Alert]:
    try:
        return dispatch(deep_alerts(deep))
    except Exception:
        logger.exception("Deep alert evaluation failed")
        return []


def recent_alerts(limit: int = 15) -> list[dict]:
    state = _load_state()
    items = [{"key": k, **v} for k, v in state.items()]
    return sorted(items, key=lambda x: x.get("sent_at", ""), reverse=True)[:limit]
