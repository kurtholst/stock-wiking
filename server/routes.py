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
