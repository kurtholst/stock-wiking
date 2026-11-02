"""Official IPC/CPC subclass titles (for hover text), via the EPO OPS classification service.

Titles are cached permanently in data/ipc_titles.json - they change only with
yearly scheme revisions. The classification service has its own, much larger
EPO quota than search, so lookups don't slow down the scans.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from .patents import _cache, _get_epo_access_token_sync

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "ipc_titles.json"
_CPC_URL = "https://ops.epo.org/3.2/rest-services/classification/cpc/{code}"
_NS = {"cpc": "http://www.epo.org/cpcexport"}
_CODE_RE = re.compile(r"^[A-HY]\d{2}[A-Z]?$")
_MAX_LOOKUPS_PER_REQUEST = 60

_lock = threading.Lock()
_titles: dict[str, str] | None = None


def _load() -> dict[str, str]:
    global _titles
    if _titles is None:
        try:
            _titles = json.loads(_CACHE_FILE.read_text()) if _CACHE_FILE.exists() else {}
        except (OSError, json.JSONDecodeError):
            _titles = {}
    return _titles


def _save(titles: dict[str, str]) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(titles, indent=1, sort_keys=True))
    tmp.replace(_CACHE_FILE)


def _tidy(title: str) -> str:
    """'HEALTHCARE INFORMATICS, i.e. ... [ICT] ...' -> 'Healthcare informatics, i.e. ... [ICT] ...'"""
    title = re.sub(r"\s+", " ", title).strip(" ;")
    lower = title.lower()
    lower = re.sub(r"\[([a-z0-9]+)\]", lambda m: f"[{m.group(1).upper()}]", lower)
    return lower[:1].upper() + lower[1:]


def _fetch_title(code: str) -> str | None:
    for attempt in range(2):
        try:
            resp = httpx.get(
                _CPC_URL.format(code=code),
                params={"depth": "0"},
                headers={"Authorization": f"Bearer {_get_epo_access_token_sync()}", "Accept": "application/xml"},
                timeout=20,
            )
        except httpx.HTTPError as e:
            logger.warning("IPC title lookup failed for %s: %s", code, e)
            return None
        if resp.status_code in (400, 401, 403) and attempt == 0:
            _cache.pop("epo_token", None)
            continue
        if resp.status_code != 200:
            return None
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            return None
        item = root.find(".//cpc:classification-item", _NS)
        if item is None:
            return None
        parts = []
        for part in item.findall("./cpc:class-title/cpc:title-part", _NS):
            text_el = part.find("./cpc:text", _NS)
            if text_el is not None:
                parts.append("".join(text_el.itertext()))
        return _tidy("; ".join(p.strip() for p in parts if p.strip())) or None
    return None


def get_ipc_titles(codes: list[str]) -> dict[str, str]:
    """Titles for IPC classes/subclasses (e.g. 'A61', 'G16H'); unknown codes are omitted."""
    wanted = sorted({c.strip().upper() for c in codes if _CODE_RE.match(c.strip().upper())})
    with _lock:
        titles = _load()
        missing = [c for c in wanted if c not in titles][:_MAX_LOOKUPS_PER_REQUEST]
        if missing:
            for code in missing:
                title = _fetch_title(code)
                if title:
                    titles[code] = title
            _save(titles)
        return {c: titles[c] for c in wanted if c in titles}
