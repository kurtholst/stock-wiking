import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .alpha import load_latest_deep, load_partial_deep, run_deep_analysis

from .analysis import (
    HistoryRequest,
    RankRequest,
    TechnicalsRequest,
    get_history,
    get_quote,
    get_rank,
    get_technicals,
    validate_ticker,
)
from .chat import ChatRequest, get_chat_response
from .db import read_tickers, write_tickers
from .ipc import get_ipc_titles
from .runner import RunBusyError, get_status, start_run
from .patents import (
    CompanySearchRequest,
    DiscoverAnalyzeRequest,
    DiscoverRequest,
    DkptoSearchRequest,
    PatentAnalyzeRequest,
    PatentSearchResponse,
    StarsScanRequest,
    _company_name_for_ticker,
    analyze_discovery_with_gemini,
    analyze_patents_with_gemini,
    discover_patents,
    load_latest_scan,
    run_stars_scan,
    search_dkpto_patents,
    search_epo_patents,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TickersPayload(BaseModel):
    tickers: list[str]


@router.get("/tickers")
def get_tickers() -> dict:
    return {"tickers": read_tickers()}


@router.put("/tickers")
def put_tickers(payload: TickersPayload) -> dict:
    write_tickers(payload.tickers)
    return {"tickers": payload.tickers}


@router.get("/quote/{ticker}")
def quote(ticker: str) -> dict:
    data = get_quote(ticker)
    return data.model_dump()


@router.get("/validate/{ticker}")
def validate(ticker: str) -> dict:
    valid = validate_ticker(ticker)
    return {"ticker": ticker, "valid": valid}


@router.post("/history")
def history(request: HistoryRequest) -> dict:
    data = get_history(request)
    return data.model_dump()


@router.post("/technicals")
def technicals(request: TechnicalsRequest) -> dict:
    data = get_technicals(request)
    return data.model_dump()


@router.post("/rank")
def rank(request: RankRequest) -> list[dict]:
    rows = get_rank(request)
    return [r.model_dump() for r in rows]


@router.post("/chat")
def chat(request: ChatRequest) -> dict:
    response = get_chat_response(request)
    return response.model_dump()


@router.get("/patents/{ticker}")
async def get_patents(ticker: str) -> dict:
    """Search EPO OPS for recent patents by portfolio company."""
    company_name = _company_name_for_ticker(ticker)
    patents, error = await search_epo_patents(company_name)
    resp = PatentSearchResponse(
        ticker=ticker,
        company_name=company_name,
        patents=patents,
        total_found=len(patents),
        source="EPO Espacenet",
        error=error,
    )
    return resp.model_dump()


@router.post("/patents/analyze")
async def post_patent_analyze(request: PatentAnalyzeRequest) -> dict:
    """Analyze patents with Gemini 2.5 Flash AI."""
    resp = await analyze_patents_with_gemini(
        patents=request.patents,
        company_name=request.company_name,
        ticker=request.ticker,
    )
    return resp.model_dump()


@router.post("/patents/discover")
def patents_discover(request: DiscoverRequest) -> dict:
    """Search EPO OPS by keyword, return grouped by company."""
    result = discover_patents(request)
    return result.model_dump()


@router.post("/patents/discover/analyze")
def patents_discover_analyze(request: DiscoverAnalyzeRequest) -> dict:
    """AI-rank the discovered companies for investment potential."""
    result = analyze_discovery_with_gemini(request)
    return result.model_dump()


@router.post("/patents/company")
async def post_patents_company(request: CompanySearchRequest) -> dict:
    """Search EPO OPS for patents by any company name."""
    patents, error = await search_epo_patents(request.company_name)
    resp = PatentSearchResponse(
        ticker="",
        company_name=request.company_name,
        patents=patents,
        total_found=len(patents),
        source="EPO Espacenet",
        error=error,
    )
    return resp.model_dump()


@router.post("/patents/dkpto")
def patents_dkpto(request: DkptoSearchRequest) -> dict:
    """Search Danish patents via EPO OPS (pn=DK*)."""
    result = search_dkpto_patents(request)
    return result.model_dump()


@router.post("/stars/scan")
def stars_scan(request: StarsScanRequest) -> dict:
    """Run a full Stars scan of Danish OMX Copenhagen companies."""
    result = run_stars_scan(request.period_days, use_cache=True)
    return result.model_dump()


@router.get("/stars/latest")
def stars_latest() -> dict | None:
    """Return the most recent Stars scan (manual or scheduled), or null if none."""
    result = load_latest_scan()
    return result.model_dump() if result else None


class AlphaRunRequest(BaseModel):
    kind: str = "stars"  # "stars" or "deep"
    period_days: int = 90
    quarters: int = 8


@router.post("/alpha/run")
def alpha_run(request: AlphaRunRequest) -> dict:
    """Start a Stars scan or a deep alpha analysis in the background."""
    if request.kind == "stars":
        def fn(progress):
            run_stars_scan(request.period_days, trigger="manual", progress=progress)
    elif request.kind == "deep":
        def fn(progress):
            run_deep_analysis(request.quarters, trigger="manual", progress=progress)
    else:
        raise HTTPException(400, f"Unknown run kind: {request.kind}")
    try:
        return start_run(request.kind, fn)
    except RunBusyError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/alpha/status")
def alpha_status() -> dict:
    return get_status()


@router.get("/alpha/deep/latest")
def alpha_deep_latest() -> dict | None:
    result = load_latest_deep()
    return result.model_dump() if result else None


@router.get("/alpha/deep/partial")
def alpha_deep_partial() -> dict | None:
    """Results so far of a deep analysis that is still running, or null."""
    result = load_partial_deep()
    return result.model_dump() if result else None


@router.get("/ipc/titles")
def ipc_titles(codes: str) -> dict[str, str]:
    """Official titles for comma-separated IPC codes, e.g. ?codes=A61K,G16H."""
    return get_ipc_titles(codes.split(","))
