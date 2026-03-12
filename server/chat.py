"""Chat module — stub without LLM backend."""

from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class TickerContext(BaseModel):
    tickers: list[str]
    quotes: list[dict] | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    ticker_context: TickerContext | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str


def get_chat_response(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        reply="Chat is not available in this standalone deployment. "
              "Use the charts, technicals, and rank table to analyse your tickers.",
        model="none",
    )
