"""Chat module - Gemini 2.5 Flash for AI Market Insights."""

from __future__ import annotations

import logging
import os

from google import genai
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a concise, expert stock market analyst. The user tracks specific "
    "tickers and will ask you about their outlook, technicals, momentum, "
    "valuations, and market trends. Use the provided ticker context (prices, "
    "changes, names) to ground your answers. Be direct, give actionable "
    "insights, and reference specific numbers. Keep answers focused and "
    "under 300 words unless the user asks for detail."
)


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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ChatResponse(
            reply="Gemini API key not configured. Set GEMINI_API_KEY in .env.",
            model="none",
        )

    # Build context block from ticker data
    context_parts: list[str] = []
    if request.ticker_context:
        context_parts.append(
            f"Tracked tickers: {', '.join(request.ticker_context.tickers)}"
        )
        if request.ticker_context.quotes:
            lines = []
            for q in request.ticker_context.quotes:
                ticker = q.get("ticker", "?")
                name = q.get("name", "")
                price = q.get("price", "?")
                chg = q.get("change_pct", 0)
                sign = "+" if chg >= 0 else ""
                lines.append(f"  {ticker} ({name}): ${price}, {sign}{chg}%")
            context_parts.append("Current quotes:\n" + "\n".join(lines))

    context_block = "\n".join(context_parts)

    # Build message history for Gemini
    contents: list[dict] = []
    for msg in request.messages:
        role = "user" if msg.role == "user" else "model"
        text = msg.content
        if role == "user" and context_block and msg == request.messages[0]:
            text = f"[Portfolio context]\n{context_block}\n\n{text}"
        contents.append({"role": role, "parts": [{"text": text}]})

    model_name = "gemini-2.5-flash"

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.7,
                "max_output_tokens": 1024,
            },
        )
        reply = response.text or "No response generated."
    except Exception:
        logger.exception("Gemini API call failed")
        return ChatResponse(
            reply="Sorry, the AI service is temporarily unavailable. Please try again.",
            model=model_name,
        )

    return ChatResponse(reply=reply, model=model_name)
