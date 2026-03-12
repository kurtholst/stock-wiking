"""Stock data fetching and technical analysis via yfinance."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import yfinance as yf
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QuoteData(BaseModel):
    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    day_high: float
    day_low: float
    week52_high: float
    week52_low: float
    market_cap: float | None = None
    volume: int | None = None
    sparkline: list[float]


class HistoryRequest(BaseModel):
    tickers: list[str]
    period: str = "1mo"


class OHLCVRow(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    change_pct: float | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None


class TickerHistory(BaseModel):
    ticker: str
    data: list[OHLCVRow]
    normalized: list[float]


class HistoryResponse(BaseModel):
    tickers: list[TickerHistory]
    dates: list[str]


class TechnicalsRequest(BaseModel):
    ticker: str
    period: str = "3y"


class TechnicalsResponse(BaseModel):
    ticker: str
    dates: list[str]
    close: list[float]
    sma20: list[float | None]
    sma50: list[float | None]
    ema12: list[float | None]
    ema26: list[float | None]
    bb_upper: list[float | None]
    bb_middle: list[float | None]
    bb_lower: list[float | None]
    rsi: list[float | None]
    macd: list[float | None]
    macd_signal: list[float | None]
    macd_hist: list[float | None]
    volume: list[int]


class RankRequest(BaseModel):
    tickers: list[str]


class RankRow(BaseModel):
    ticker: str
    price: float
    change_1d: float | None = None
    change_1w: float | None = None
    change_1m: float | None = None
    change_3m: float | None = None
    rsi14: float | None = None
    macd_hist: float | None = None
    bb_pct: float | None = None
    ma20_dist: float | None = None
    ma50_dist: float | None = None
    ma200_dist: float | None = None
    vol_ratio: float | None = None
    atr14: float | None = None


# ---------------------------------------------------------------------------
# Period mapping for yfinance
# ---------------------------------------------------------------------------

_YF_PERIOD = {
    "5d": "5d", "1mo": "1mo", "3mo": "3mo", "6mo": "6mo",
    "1y": "1y", "2y": "2y", "3y": "5y", "5y": "5y", "max": "max",
}

_PERIOD_DAYS = {
    "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180,
    "1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "max": 9999,
}


def _fetch_ohlcv(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance."""
    yf_period = _YF_PERIOD.get(period, "1y")
    t = yf.Ticker(ticker)
    df = t.history(period=yf_period, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"
    for col in ("Open", "High", "Low", "Close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)
    return df.dropna(subset=["Close"])


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def validate_ticker(ticker: str) -> bool:
    """Validate ticker by checking if yfinance can find it."""
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9\-\.]{0,14}$', ticker):
        return False
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return info.get("regularMarketPrice") is not None or info.get("currentPrice") is not None
    except Exception:
        return False


def get_quote(ticker: str) -> QuoteData:
    """Get current quote from yfinance."""
    t = yf.Ticker(ticker)
    info = t.info

    price = info.get("regularMarketPrice") or info.get("currentPrice") or 0.0
    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose") or price
    change = round(price - prev_close, 2)
    change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

    # Sparkline from last 30 days
    hist = t.history(period="1mo", auto_adjust=True)
    sparkline = [round(float(v), 2) for v in hist["Close"].dropna()] if not hist.empty else []

    return QuoteData(
        ticker=ticker,
        name=info.get("shortName") or info.get("longName") or ticker,
        price=round(price, 2),
        change=change,
        change_pct=change_pct,
        day_high=round(info.get("dayHigh") or info.get("regularMarketDayHigh") or 0.0, 2),
        day_low=round(info.get("dayLow") or info.get("regularMarketDayLow") or 0.0, 2),
        week52_high=round(info.get("fiftyTwoWeekHigh") or 0.0, 2),
        week52_low=round(info.get("fiftyTwoWeekLow") or 0.0, 2),
        market_cap=info.get("marketCap"),
        volume=info.get("volume") or info.get("regularMarketVolume"),
        sparkline=sparkline,
    )


def _fetch_one_ticker(ticker: str, period: str) -> TickerHistory | None:
    """Fetch history for a single ticker."""
    try:
        # Fetch enough extra data for MA-200 computation
        fetch_period = "5y" if period in ("3y", "5y", "max") else "2y"

        full_hist = _fetch_ohlcv(ticker, fetch_period)
        if full_hist.empty:
            return None

        # Compute indicators on full history
        close_series = full_hist["Close"]
        pct_change = close_series.pct_change() * 100
        ma20 = close_series.rolling(window=20).mean()
        ma50 = close_series.rolling(window=50).mean()
        ma200 = close_series.rolling(window=200).mean()

        # Determine display window
        display_days = _PERIOD_DAYS.get(period, 30)

        if display_days < 9999:
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=display_days)
            display_n = int((full_hist.index >= cutoff).sum())
        else:
            display_n = len(full_hist)

        if display_n == 0:
            display_n = len(full_hist)

        full_hist = full_hist.iloc[-display_n:]
        pct_change = pct_change.iloc[-display_n:]
        ma20 = ma20.iloc[-display_n:]
        ma50 = ma50.iloc[-display_n:]
        ma200 = ma200.iloc[-display_n:]

        dates = [d.strftime("%Y-%m-%d") for d in full_hist.index]
        closes = full_hist["Close"].tolist()
        base = closes[0] if closes else 1.0
        normalized = [round((c / base - 1) * 100, 2) for c in closes]

        def _safe(v: float) -> float:
            return 0.0 if pd.isna(v) else round(v, 2)

        def _safe_or_none(v: float) -> float | None:
            return None if pd.isna(v) else round(v, 2)

        rows = [
            OHLCVRow(
                date=d,
                open=_safe(row.Open),
                high=_safe(row.High),
                low=_safe(row.Low),
                close=_safe(row.Close),
                volume=int(row.Volume) if not pd.isna(row.Volume) else 0,
                change_pct=_safe_or_none(pct),
                ma20=_safe_or_none(m20),
                ma50=_safe_or_none(m50),
                ma200=_safe_or_none(m200),
            )
            for d, row, pct, m20, m50, m200 in zip(
                dates, full_hist.itertuples(), pct_change, ma20, ma50, ma200
            )
        ]

        return TickerHistory(ticker=ticker, data=rows, normalized=normalized)
    except Exception:
        logger.exception("Failed to fetch history for %s", ticker)
        return None


def get_history(request: HistoryRequest) -> HistoryResponse:
    with ThreadPoolExecutor(max_workers=min(len(request.tickers), 5)) as pool:
        futures = [pool.submit(_fetch_one_ticker, t, request.period) for t in request.tickers]
        results = [f.result() for f in futures]

    ticker_histories = [r for r in results if r is not None]
    all_dates = ticker_histories[0].data and [row.date for row in ticker_histories[0].data] if ticker_histories else []

    return HistoryResponse(tickers=ticker_histories, dates=all_dates)


# ---------------------------------------------------------------------------
# Technical indicators
# ---------------------------------------------------------------------------

def _sma(series: pd.Series, window: int) -> list[float | None]:
    result = series.rolling(window=window).mean()
    return [None if pd.isna(v) else round(v, 2) for v in result]


def _ema(series: pd.Series, span: int) -> list[float | None]:
    result = series.ewm(span=span, adjust=False).mean()
    return [None if pd.isna(v) else round(v, 2) for v in result]


def _bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0):
    middle = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    to_list = lambda s: [None if pd.isna(v) else round(v, 2) for v in s]
    return to_list(upper), to_list(middle), to_list(lower)


def _rsi(series: pd.Series, period: int = 14) -> list[float | None]:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return [None if pd.isna(v) else round(v, 2) for v in rsi]


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    to_list = lambda s: [None if pd.isna(v) else round(v, 4) for v in s]
    return to_list(macd_line), to_list(signal_line), to_list(histogram)


def get_technicals(request: TechnicalsRequest) -> TechnicalsResponse:
    hist = _fetch_ohlcv(request.ticker, request.period)
    if hist.empty:
        raise ValueError(f"No OHLCV data for {request.ticker}")

    close = hist["Close"]
    dates = [d.strftime("%Y-%m-%d") for d in hist.index]

    bb_upper, bb_middle, bb_lower = _bollinger(close)
    macd_line, macd_signal, macd_hist = _macd(close)

    return TechnicalsResponse(
        ticker=request.ticker,
        dates=dates,
        close=[round(v, 2) for v in close],
        sma20=_sma(close, 20),
        sma50=_sma(close, 50),
        ema12=_ema(close, 12),
        ema26=_ema(close, 26),
        bb_upper=bb_upper,
        bb_middle=bb_middle,
        bb_lower=bb_lower,
        rsi=_rsi(close),
        macd=macd_line,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        volume=[int(v) for v in hist["Volume"]],
    )


# ---------------------------------------------------------------------------
# Rank (one-row-per-ticker snapshot)
# ---------------------------------------------------------------------------

def _fetch_rank_row(ticker: str) -> RankRow | None:
    """Compute a single RankRow from 1y daily data."""
    try:
        hist = _fetch_ohlcv(ticker, "1y")
        if hist.empty or len(hist) < 2:
            return None

        close = hist["Close"]
        volume = hist["Volume"]
        high = hist["High"]
        low = hist["Low"]
        n = len(close)

        latest_close = round(float(close.iloc[-1]), 2)

        def _pct_return(days: int) -> float | None:
            if n <= days:
                return None
            prev = float(close.iloc[-1 - days])
            return round((latest_close - prev) / prev * 100, 2) if prev else None

        rsi_vals = _rsi(close)
        rsi14 = rsi_vals[-1] if rsi_vals and rsi_vals[-1] is not None else None

        _, _, macd_h = _macd(close)
        macd_hist_val = macd_h[-1] if macd_h and macd_h[-1] is not None else None

        bb_u, _, bb_l = _bollinger(close)
        bb_upper_val = bb_u[-1]
        bb_lower_val = bb_l[-1]
        bb_pct = None
        if bb_upper_val is not None and bb_lower_val is not None and bb_upper_val != bb_lower_val:
            bb_pct = round((latest_close - bb_lower_val) / (bb_upper_val - bb_lower_val) * 100, 2)

        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        def _ma_dist(ma: pd.Series) -> float | None:
            v = ma.iloc[-1]
            if pd.isna(v) or v == 0:
                return None
            return round((latest_close - v) / v * 100, 2)

        vol_sma20 = volume.rolling(20).mean()
        last_vol = float(volume.iloc[-1])
        last_vol_avg = float(vol_sma20.iloc[-1]) if not pd.isna(vol_sma20.iloc[-1]) else None
        vol_ratio = round(last_vol / last_vol_avg, 2) if last_vol_avg and last_vol_avg > 0 else None

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        atr14 = round(float(atr.iloc[-1]), 2) if not pd.isna(atr.iloc[-1]) else None

        return RankRow(
            ticker=ticker,
            price=latest_close,
            change_1d=_pct_return(1),
            change_1w=_pct_return(5),
            change_1m=_pct_return(21),
            change_3m=_pct_return(63),
            rsi14=rsi14,
            macd_hist=macd_hist_val,
            bb_pct=bb_pct,
            ma20_dist=_ma_dist(ma20),
            ma50_dist=_ma_dist(ma50),
            ma200_dist=_ma_dist(ma200),
            vol_ratio=vol_ratio,
            atr14=atr14,
        )
    except Exception:
        logger.exception("Failed to fetch rank for %s", ticker)
        return None


def get_rank(request: RankRequest) -> list[RankRow]:
    with ThreadPoolExecutor(max_workers=min(len(request.tickers), 5)) as pool:
        futures = [pool.submit(_fetch_rank_row, t) for t in request.tickers]
        results = [f.result() for f in futures]

    return [r for r in results if r is not None]
