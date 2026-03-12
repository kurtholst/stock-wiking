"""Local ticker storage using a YAML file."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

_TICKERS_FILE = Path(os.path.dirname(os.path.dirname(__file__))) / "tickers.yaml"


def read_tickers() -> list[str]:
    """Read tickers from tickers.yaml."""
    if not _TICKERS_FILE.exists():
        return []
    data = yaml.safe_load(_TICKERS_FILE.read_text()) or {}
    return data.get("tickers", [])


def write_tickers(tickers: list[str]) -> None:
    """Write tickers to tickers.yaml."""
    _TICKERS_FILE.write_text(yaml.dump({"tickers": tickers}, default_flow_style=False))
