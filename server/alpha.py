"""Deep alpha analysis - patent submission-area shifts over multiple quarters.

Goes beyond the Stars scan:
- quarterly filing history per company (true EPO totals + IPC/office samples)
- shift trajectory (is the mix change accelerating?) and filing velocity
- emerging technology classes, new filing offices, new co-applicants
- share-price context (has the market reacted yet?)
- a transparent composite Alpha Score
- an AI thesis per top candidate and a cross-company memo (Gemini with a large
  thinking budget; defaults to free-tier Flash models, override with GEMINI_DEEP_MODEL)
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from collections import defaultdict
from pathlib import Path

import httpx
from pydantic import BaseModel

from .alerts import notify_deep
from .patents import (
    DANISH_COMPANIES,
    DanishCompany,
    GeminiError,
    StarsPatentHit,
    _ipc_counts,
    _office_counts,
    _share,
    _top,
    _tvd,
    epo_applicant_search,
    gemini_json,
    load_latest_scan,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEEP_LATEST_FILE = _DATA_DIR / "alpha_deep_latest.json"
_DEEP_PARTIAL_FILE = _DATA_DIR / "alpha_deep_partial.json"  # live results of a run in progress

_QUARTER_DAYS = 91
_RECENT_QUARTERS = 2          # "now" = the last two quarters; everything before is the baseline
_SAMPLE_PER_QUARTER = 50      # patents sampled per applicant name and quarter
_AI_TOP_N = 6                 # companies that get an AI thesis


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class QuarterStat(BaseModel):
    label: str               # e.g. "Aug 26" (start month of the 91-day window)
    start: str
    end: str
    total: int | None        # EPO total publications (None = lookup failed)
    sample: int              # patents sampled for the mix
    ipc_shift: float | None  # mix vs. all earlier quarters pooled


class EmergingArea(BaseModel):
    code: str
    recent_count: int
    first_seen: str
    examples: list[str]


class CoApplicant(BaseModel):
    name: str
    count: int
    first_seen: str
    new: bool


class DeepThesis(BaseModel):
    move_type: str           # PIVOT / DIVERSIFICATION / FOCUS / GEOGRAPHIC_EXPANSION / PARTNERSHIP / M&A_INTEGRATION / DEFENSIVE / NOISE
    hypothesis: str
    conviction: int          # 1-5
    horizon: str
    priced_in: str           # LOW / MEDIUM / HIGH
    catalysts: list[str]
    risks: list[str]
    confirm_signals: list[str]
    refute_signals: list[str]


class DeepCompany(BaseModel):
    name: str
    ticker: str
    sector: str
    stars: int | None = None
    ai_signal: str | None = None
    data_complete: bool = True
    quarters: list[QuarterStat]
    recent_total: int | None = None
    baseline_avg: float | None = None
    velocity_ratio: float | None = None
    recent_shift: float | None = None
    office_shift: float | None = None
    shift_trend: str | None = None      # ACCELERATING / STABLE / FADING
    top_ipc_recent: list[str] = []
    top_ipc_baseline: list[str] = []
    emerging: list[EmergingArea] = []
    new_offices: list[str] = []
    co_applicants: list[CoApplicant] = []
    return_3m: float | None = None
    return_6m: float | None = None
    from_52w_high: float | None = None
    alpha_score: float = 0.0
    score_breakdown: dict[str, float] = {}
    thesis: DeepThesis | None = None


class IpcLabel(BaseModel):
    code: str
    label: str


class Theme(BaseModel):
    code: str
    companies: list[str]


class AlphaDeepResponse(BaseModel):
    run_at: str
    finished_at: str
    duration_s: int
    trigger: str
    quarters: int
    companies: list[DeepCompany]
    themes: list[Theme]
    ipc_labels: list[IpcLabel]
    memo: str
    model: str
    warnings: list[str]
    in_progress: bool = False
    phase: str = "done"          # data | ai | memo | done
    companies_done: int = 0
    companies_total: int = 0


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _quarter_windows(n: int, today: datetime.date) -> list[tuple[datetime.date, datetime.date]]:
    """n rolling 91-day windows ending today, oldest first."""
    windows = []
    end = today
    for _ in range(n):
        start = end - datetime.timedelta(days=_QUARTER_DAYS - 1)
        windows.append((start, end))
        end = start - datetime.timedelta(days=1)
    return list(reversed(windows))


def _is_own_applicant(name: str, company: DanishCompany) -> bool:
    own = [company.name.upper(), *company.epo_names]
    return any(o in name for o in own)


def _price_context(ticker: str) -> tuple[float | None, float | None, float | None]:
    """(3M return, 6M return, distance from 52-week high) as fractions."""
    try:
        import yfinance as yf

        close = yf.Ticker(ticker).history(period="1y")["Close"].dropna()
        if len(close) < 30:
            return None, None, None
        last = float(close.iloc[-1])
        r3 = last / float(close.iloc[-63]) - 1 if len(close) > 63 else None
        r6 = last / float(close.iloc[-126]) - 1 if len(close) > 126 else None
        return r3, r6, last / float(close.max()) - 1
    except Exception:
        return None, None, None


def _analyze_company(company: DanishCompany, quarters: int, today: datetime.date, progress) -> DeepCompany:
    windows = _quarter_windows(quarters, today)
    q_hits: list[list[StarsPatentHit]] = []
    stats: list[QuarterStat] = []
    complete = True

    for qi, (start, end) in enumerate(windows):
        progress(f"{company.name}: quarter {qi + 1}/{quarters}")
        seen: set[str] = set()
        hits: list[StarsPatentHit] = []
        total: int | None = 0
        for epo_name in company.epo_names:
            res = epo_applicant_search(
                epo_name, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), _SAMPLE_PER_QUARTER,
            )
            if res is None:
                complete = False
                total = None
                continue
            if total is not None:
                total += res[1]
            for h in res[0]:
                if h.patent_number not in seen:
                    seen.add(h.patent_number)
                    hits.append(h)
        q_hits.append(hits)
        stats.append(QuarterStat(
            label=start.strftime("%b %y"), start=start.isoformat(), end=end.isoformat(),
            total=total, sample=len(hits), ipc_shift=None,
        ))

    # Shift trajectory: each quarter's mix vs. everything before it
    for qi in range(1, quarters):
        before = [h for q in q_hits[:qi] for h in q]
        if len(q_hits[qi]) >= 3 and len(before) >= 5:
            stats[qi].ipc_shift = _tvd(_share(_ipc_counts(q_hits[qi])), _share(_ipc_counts(before)))

    split = max(quarters - _RECENT_QUARTERS, 1)
    recent = [h for q in q_hits[split:] for h in q]
    baseline = [h for q in q_hits[:split] for h in q]
    ipc_r, ipc_b = _ipc_counts(recent), _ipc_counts(baseline)
    off_r, off_b = _office_counts(recent), _office_counts(baseline)

    dc = DeepCompany(
        name=company.name, ticker=company.ticker, sector=company.sector,
        data_complete=complete, quarters=stats,
        top_ipc_recent=_top(ipc_r, 4), top_ipc_baseline=_top(ipc_b, 4),
    )

    totals_recent = [s.total for s in stats[split:]]
    totals_base = [s.total for s in stats[:split]]
    if None not in totals_recent:
        dc.recent_total = sum(totals_recent)  # type: ignore[arg-type]
    if totals_base and None not in totals_base:
        dc.baseline_avg = round(sum(totals_base) / len(totals_base), 1)  # type: ignore[arg-type]
    if dc.recent_total is not None and dc.baseline_avg:
        dc.velocity_ratio = round((dc.recent_total / _RECENT_QUARTERS) / dc.baseline_avg, 2)

    if len(recent) >= 3 and len(baseline) >= 5:
        dc.recent_shift = _tvd(_share(ipc_r), _share(ipc_b))
        if off_r and off_b:
            dc.office_shift = _tvd(_share(off_r), _share(off_b))

    trajectory = [s.ipc_shift for s in stats if s.ipc_shift is not None]
    if len(trajectory) >= 3:
        late, early = trajectory[-1], sum(trajectory[:-1]) / len(trajectory[:-1])
        dc.shift_trend = "ACCELERATING" if late > early + 0.1 else "FADING" if late < early - 0.1 else "STABLE"

    # Emerging classes: >=2 recent patents, none in the baseline
    if baseline:
        for code in _top(ipc_r, 15):
            if code in ipc_b:
                continue
            with_code = [h for h in recent if code in h.ipc]
            if len(with_code) < 2:
                continue
            first_q = next(stats[i].label for i, q in enumerate(q_hits) if any(code in h.ipc for h in q))
            dc.emerging.append(EmergingArea(
                code=code, recent_count=len(with_code), first_seen=first_q,
                examples=[h.title for h in with_code[:3]],
            ))
        dc.new_offices = [o for o in _top(off_r, 10) if o not in off_b]

    # Co-applicants (partners, universities, acquired entities)
    co: dict[str, dict] = {}
    for qi, q in enumerate(q_hits):
        for h in q:
            for a in h.applicants:
                if _is_own_applicant(a, company):
                    continue
                entry = co.setdefault(a, {"count": 0, "first_q": qi})
                entry["count"] += 1
    dc.co_applicants = sorted(
        (CoApplicant(name=n, count=v["count"], first_seen=stats[v["first_q"]].label,
                     new=bool(baseline) and v["first_q"] >= split)
         for n, v in co.items()),
        key=lambda c: (c.new, c.count), reverse=True,
    )[:8]

    dc.return_3m, dc.return_6m, dc.from_52w_high = _price_context(company.ticker)
    return dc


# ---------------------------------------------------------------------------
# Alpha Score
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def score_company(dc: DeepCompany) -> None:
    """Composite 0-100 score; each component is visible in score_breakdown."""
    new_partners = sum(1 for c in dc.co_applicants if c.new)
    b = {
        "shift": 25 * _clamp((dc.recent_shift or 0) / 0.6),
        "novelty": 20 * _clamp(len(dc.emerging) / 3),
        "velocity": 15 * _clamp(((dc.velocity_ratio or 1) - 1) / 1.0),
        "international": 10 * _clamp(len(dc.new_offices) / 2),
        "partners": 10 * _clamp(new_partners / 2),
        "stars": 10 * (dc.stars or 0) / 5,
    }
    # Under-reaction only counts when there is a strategic change to under-react to
    change = _clamp((b["shift"] + b["novelty"]) / 25)
    if dc.return_6m is not None:
        b["under_reaction"] = 10 * _clamp((0.10 - dc.return_6m) / 0.30) * change
    else:
        b["under_reaction"] = 0.0
    if dc.shift_trend == "ACCELERATING":
        b["shift"] = min(25.0, b["shift"] * 1.2)
    dc.score_breakdown = {k: round(v, 1) for k, v in b.items()}
    dc.alpha_score = round(sum(b.values()), 1)


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

# Free-tier friendly defaults. Gemini free-tier quotas are per model, so each
# step of the chain is a separate quota; Flash-Lite is the last resort.
_DEFAULT_DEEP_MODEL = "gemini-flash-latest"
_DEFAULT_FALLBACK_MODEL = "gemini-2.5-flash"
_LAST_RESORT_MODEL = "gemini-flash-lite-latest"


def _model_chain() -> list[tuple[str, int]]:
    """(model, thinking budget) in the order to try them, without duplicates."""
    chain = [
        (os.environ.get("GEMINI_DEEP_MODEL", _DEFAULT_DEEP_MODEL), 16384),
        (os.environ.get("GEMINI_MODEL", _DEFAULT_FALLBACK_MODEL), 8192),
        (_LAST_RESORT_MODEL, 4096),
    ]
    seen: set[str] = set()
    return [(m, b) for m, b in chain if not (m in seen or seen.add(m))]


def _call_ai(system: str, user: str, schema: dict, warnings: list[str]) -> tuple[dict | None, str | None]:
    """Try each model in the chain (2 attempts each).

    Returns (data, model that produced it), or (None, None) if every model failed.
    """
    chain = _model_chain()
    for i, (model, budget) in enumerate(chain):
        for attempt in range(2):
            try:
                return gemini_json(model, system, user, schema, thinking_budget=budget, timeout=300), model
            except (GeminiError, httpx.HTTPError, ValueError) as e:
                logger.warning("Gemini %s failed (attempt %d): %s", model, attempt + 1, e)
                if attempt == 0:
                    time.sleep(5)
        if i + 1 < len(chain):
            warnings.append(f"AI model {model} unavailable, fell back to {chain[i + 1][0]}")
    warnings.append("All AI models failed - no AI output for this step")
    return None, None


_THESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "move_type": {"type": "string", "enum": [
            "PIVOT", "DIVERSIFICATION", "FOCUS", "GEOGRAPHIC_EXPANSION",
            "PARTNERSHIP", "M&A_INTEGRATION", "DEFENSIVE", "NOISE",
        ]},
        "hypothesis": {"type": "string"},
        "conviction": {"type": "integer"},
        "horizon": {"type": "string"},
        "priced_in": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "catalysts": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "confirm_signals": {"type": "array", "items": {"type": "string"}},
        "refute_signals": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["move_type", "hypothesis", "conviction", "horizon", "priced_in",
                 "catalysts", "risks", "confirm_signals", "refute_signals"],
}

_THESIS_SYSTEM = (
    "You are a buy-side equity analyst specialising in patent intelligence for Nordic listed companies. "
    "You get hard evidence about one company's patent publications over several quarters. "
    "Your job: decide whether a change in WHAT (IPC technology classes) or WHERE (filing offices) the company "
    "files reveals a strategic move the market may not have priced in.\n"
    "Rules:\n"
    "- Reason from the evidence. Translate IPC codes into plain technology areas.\n"
    "- Remember the ~18-month publication lag: published filings reflect decisions made 1.5-2 years ago.\n"
    "- Consider mundane explanations (acquired portfolios, continuation filings, small samples, "
    "defensive filings, name collisions with other applicants) and choose NOISE if they dominate.\n"
    "- conviction 1-5 (5 = strong, specific, under-appreciated move). Be sceptical; most cases are 1-3.\n"
    "- priced_in: judge from share-price behaviour and how visible the move already is.\n"
    "- Catalysts, risks, confirm and refute signals must be concrete and checkable (events, data sources, metrics).\n"
    "- Keep hypothesis to 3-5 sentences. Write in English."
)


def _thesis_prompt(dc: DeepCompany, stars_summary: str | None) -> str:
    def pct(v):
        return "n/a" if v is None else f"{v * 100:+.1f}%"

    lines = [
        f"Company: {dc.name} ({dc.ticker}), sector {dc.sector}",
        f"Stars rating: {dc.stars or 'n/a'}/5, Stars AI signal: {dc.ai_signal or 'n/a'}",
        f"Stars AI comment: {stars_summary or 'n/a'}",
        f"Data complete: {dc.data_complete}",
        "Quarterly EPO publications (total / sampled / mix shift vs. earlier quarters):",
        *[f"  {q.label}: {q.total if q.total is not None else 'failed'} / {q.sample} / "
          f"{'n/a' if q.ipc_shift is None else f'{q.ipc_shift:.0%}'}" for q in dc.quarters],
        f"Velocity ratio (recent quarterly avg vs baseline avg): {dc.velocity_ratio}",
        f"Technology-mix shift recent vs baseline: {dc.recent_shift}, trend: {dc.shift_trend}",
        f"Filing-office shift: {dc.office_shift}, new offices: {', '.join(dc.new_offices) or 'none'}",
        f"Top IPC baseline: {', '.join(dc.top_ipc_baseline) or 'n/a'}; top IPC recent: {', '.join(dc.top_ipc_recent) or 'n/a'}",
        "Emerging IPC classes (absent from baseline):",
        *([f"  {e.code} - {e.recent_count} patents, first seen {e.first_seen}; e.g. " + " | ".join(e.examples)
           for e in dc.emerging] or ["  none"]),
        "Co-applicants:",
        *([f"  {c.name} - {c.count} patents, first seen {c.first_seen}{' (NEW)' if c.new else ''}"
           for c in dc.co_applicants] or ["  none"]),
        f"Share price: 3M {pct(dc.return_3m)}, 6M {pct(dc.return_6m)}, vs 52w high {pct(dc.from_52w_high)}",
        f"Alpha Score {dc.alpha_score}/100, components: {dc.score_breakdown}",
    ]
    return "\n".join(lines)


_MEMO_SCHEMA = {
    "type": "object",
    "properties": {
        "memo": {"type": "string"},
        "ipc_labels": {"type": "array", "items": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "label": {"type": "string"}},
            "required": ["code", "label"],
        }},
    },
    "required": ["memo", "ipc_labels"],
}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_deep_analysis(quarters: int = 8, trigger: str = "manual", progress=None) -> AlphaDeepResponse:
    started = time.monotonic()
    run_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    today = datetime.date.today()
    warnings: list[str] = []
    quarters = max(4, min(quarters, 16))

    stars = load_latest_scan()
    stars_by_ticker = {c.ticker: c for c in stars.companies} if stars else {}
    if not stars:
        warnings.append("No Stars scan found - star ratings are missing from the score")

    n_companies = len(DANISH_COMPANIES)
    total_steps = n_companies + _AI_TOP_N + 1

    def step(i: int, msg: str) -> None:
        if progress:
            progress(i, total_steps, msg)

    companies: list[DeepCompany] = []
    models_used: list[str] = []  # models that actually produced output

    def model_label() -> str:
        return ", ".join(models_used) or _model_chain()[0][0]

    def note_model(model: str | None) -> None:
        if model and model not in models_used:
            models_used.append(model)

    def publish(phase: str, memo: str = "") -> None:
        """Write the results so far, so the UI can show them while the run continues."""
        _save(AlphaDeepResponse(
            run_at=run_at,
            finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            duration_s=round(time.monotonic() - started),
            trigger=trigger,
            quarters=quarters,
            companies=sorted(companies, key=lambda c: c.alpha_score, reverse=True),
            themes=[],
            ipc_labels=[],
            memo=memo,
            model=model_label(),
            warnings=list(dict.fromkeys(warnings)),
            in_progress=True,
            phase=phase,
            companies_done=len(companies),
            companies_total=n_companies,
        ), _DEEP_PARTIAL_FILE)

    _DEEP_PARTIAL_FILE.unlink(missing_ok=True)
    for i, company in enumerate(DANISH_COMPANIES):
        dc = _analyze_company(company, quarters, today, lambda m, i=i: step(i, m))
        sc = stars_by_ticker.get(company.ticker)
        if sc:
            dc.stars, dc.ai_signal = sc.stars, sc.ai_signal
        if not dc.data_complete:
            warnings.append(f"{company.name}: some EPO lookups failed - figures are lower bounds")
        score_company(dc)
        companies.append(dc)
        publish("data")

    companies.sort(key=lambda c: c.alpha_score, reverse=True)
    publish("ai")

    # AI thesis for the top candidates
    candidates = [c for c in companies if c.alpha_score > 0 and any(q.sample for q in c.quarters)][:_AI_TOP_N]
    for j, dc in enumerate(candidates):
        step(n_companies + j, f"AI deep dive: {dc.name}")
        sc = stars_by_ticker.get(dc.ticker)
        data, model = _call_ai(_THESIS_SYSTEM, _thesis_prompt(dc, sc.ai_summary if sc else None), _THESIS_SCHEMA, warnings)
        note_model(model)
        if data:
            data["conviction"] = max(1, min(5, int(data.get("conviction", 1))))
            dc.thesis = DeepThesis(**data)
            publish("ai")

    # Cross-company themes: emerging classes shared by 2+ companies
    by_code: dict[str, list[str]] = defaultdict(list)
    for dc in companies:
        for e in dc.emerging:
            by_code[e.code].append(dc.name)
    themes = sorted(
        (Theme(code=k, companies=v) for k, v in by_code.items() if len(v) >= 2),
        key=lambda t: len(t.companies), reverse=True,
    )

    step(n_companies + _AI_TOP_N, "Writing analyst memo")
    publish("memo")
    all_codes = sorted({c for dc in companies for c in [*(e.code for e in dc.emerging), *dc.top_ipc_recent]})
    memo_input = "\n\n".join(
        f"{dc.name} ({dc.ticker}) score {dc.alpha_score}: shift {dc.recent_shift}, trend {dc.shift_trend}, "
        f"velocity {dc.velocity_ratio}, emerging {[e.code for e in dc.emerging]}, new offices {dc.new_offices}, "
        f"new partners {[c.name for c in dc.co_applicants if c.new]}, 6M return {dc.return_6m}"
        + (f"\nThesis ({dc.thesis.move_type}, conviction {dc.thesis.conviction}, priced in {dc.thesis.priced_in}): "
           f"{dc.thesis.hypothesis}" if dc.thesis else "")
        for dc in companies if any(q.sample for q in dc.quarters)
    )
    memo_system = (
        "You are the head of research writing a short internal memo (max ~250 words, English, plain text with "
        "short paragraphs) on patent-based alpha signals across Danish listed companies. Lead with the 1-3 most "
        "actionable ideas, then cross-company themes (shared emerging technology classes: "
        f"{[(t.code, t.companies) for t in themes] or 'none'}), then what to monitor next. Be sceptical and specific. "
        "Also return a short plain-English label (max 6 words) for every IPC subclass code listed."
    )
    memo_data, memo_model = _call_ai(
        memo_system, f"IPC codes to label: {', '.join(all_codes)}\n\nCompanies:\n{memo_input}", _MEMO_SCHEMA, warnings,
    )
    note_model(memo_model)

    response = AlphaDeepResponse(
        run_at=run_at,
        finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        duration_s=round(time.monotonic() - started),
        trigger=trigger,
        quarters=quarters,
        companies=companies,
        themes=themes,
        ipc_labels=[IpcLabel(**x) for x in (memo_data or {}).get("ipc_labels", [])],
        memo=(memo_data or {}).get("memo", "AI memo unavailable."),
        model=model_label(),
        warnings=list(dict.fromkeys(warnings)),
    )
    _save(response)
    _DEEP_PARTIAL_FILE.unlink(missing_ok=True)
    notify_deep(response)
    return response


def _save(response: AlphaDeepResponse, path: Path = _DEEP_LATEST_FILE) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(response.model_dump_json(indent=2))
    tmp.replace(path)


def _load(path: Path) -> AlphaDeepResponse | None:
    if not path.exists():
        return None
    try:
        return AlphaDeepResponse.model_validate_json(path.read_text())
    except Exception:
        logger.exception("Could not read %s", path.name)
        return None


def load_latest_deep() -> AlphaDeepResponse | None:
    return _load(_DEEP_LATEST_FILE)


def load_partial_deep() -> AlphaDeepResponse | None:
    """Results so far of a deep run in progress (None if no run is in progress)."""
    return _load(_DEEP_PARTIAL_FILE)
