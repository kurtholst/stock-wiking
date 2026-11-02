import logging

from fastapi import APIRouter
from pydantic import BaseModel

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
    result = run_stars_scan(request.period_days)
    return result.model_dump()
