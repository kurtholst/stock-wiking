"""Patent search (EPO OPS API) and AI analysis (Gemini 2.5 Flash).

Contains both:
- Per-ticker patent search (Patent AI tab)
- Technology keyword discovery (Company Search tab)
"""

import base64
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models - Per-ticker patent search (existing Patent AI tab)
# ---------------------------------------------------------------------------

class PatentResult(BaseModel):
    patent_number: str
    title: str
    applicant: str
    filing_date: str | None = None
    status: str | None = None


class PatentScore(BaseModel):
    patent_number: str
    title: str
    score: str  # "POSITIVE" | "INSIGNIFICANT" | "NEGATIVE"
    reasoning: str


class PatentSearchRequest(BaseModel):
    ticker: str


class PatentAnalyzeRequest(BaseModel):
    ticker: str
    company_name: str
    patents: list[PatentResult]


class PatentSearchResponse(BaseModel):
    ticker: str
    company_name: str
    patents: list[PatentResult]
    total_found: int
    source: str
    error: str | None = None


class PatentAnalyzeResponse(BaseModel):
    ticker: str
    company_name: str
    scores: list[PatentScore]
    summary: str
    model: str


# ---------------------------------------------------------------------------
# Pydantic models - Company discovery (new Company Search tab)
# ---------------------------------------------------------------------------

class DiscoverPatentResult(BaseModel):
    title: str
    patent_number: str
    date: str | None = None
    applicant: str


class DiscoverRequest(BaseModel):
    query: str
    ipc: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class CompanyPatents(BaseModel):
    company: str
    patent_count: int
    sample_patents: list[DiscoverPatentResult]


class DiscoverResponse(BaseModel):
    query: str
    companies: list[CompanyPatents]
    total_patents: int
    source: str = "EPO Espacenet"
    error: str | None = None


class CompanyRanking(BaseModel):
    company: str
    score: str
    reasoning: str
    patent_count: int


class DiscoverAnalyzeRequest(BaseModel):
    query: str
    companies: list[CompanyPatents]


class DiscoverAnalyzeResponse(BaseModel):
    query: str
    rankings: list[CompanyRanking]
    summary: str
    model: str


# ---------------------------------------------------------------------------
# Pydantic models - Company AI (search by any company name)
# ---------------------------------------------------------------------------

class CompanySearchRequest(BaseModel):
    company_name: str


# ---------------------------------------------------------------------------
# Pydantic models - Stars (Danish patent screener)
# ---------------------------------------------------------------------------

class DanishCompany(BaseModel):
    name: str
    ticker: str
    epo_names: list[str]
    sector: str


class StarsPatentHit(BaseModel):
    patent_number: str
    title: str
    applicant: str
    filing_date: str | None = None
    publication_date: str | None = None
    ipc: list[str] = []  # IPC subclasses, e.g. "A61K"
    applicants: list[str] = []


class AreaShift(BaseModel):
    """Change in a company's patent mix: scan window vs. the prior 12 months."""
    baseline_count: int = 0
    recent_count: int = 0
    ipc_shift: float | None = None           # total variation distance 0..1
    office_shift: float | None = None        # total variation distance 0..1
    new_ipc: list[str] = []                  # subclasses absent from the baseline
    new_offices: list[str] = []              # filing offices absent from the baseline
    top_ipc_recent: list[str] = []
    top_ipc_baseline: list[str] = []
    flagged: bool = False
    data_complete: bool = True   # False if an EPO lookup failed (counts are lower bounds)


class CompanyStarsResult(BaseModel):
    name: str
    ticker: str
    sector: str
    patent_count: int
    recent_patents: list[StarsPatentHit]
    stars: int | None = None
    ai_signal: str | None = None
    ai_summary: str | None = None
    stock_price: float | None = None
    stock_change_pct: float | None = None
    area_shift: AreaShift | None = None


class StarsScanRequest(BaseModel):
    period_days: int = 90


class StarsScanResponse(BaseModel):
    scan_date: str
    period_days: int
    companies: list[CompanyStarsResult]
    total_patents: int
    summary: str
    model: str
    run_at: str | None = None    # ISO timestamp (UTC) of when the scan ran
    trigger: str | None = None   # "manual" or "scheduled"


# ---------------------------------------------------------------------------
# Pydantic models - DKPTO (Danish patent search via EPO)
# ---------------------------------------------------------------------------

class DkptoSearchRequest(BaseModel):
    applicant: str | None = None
    title: str | None = None
    ipc: str | None = None
    date_from: str | None = None   # YYYY or YYYYMMDD
    date_to: str | None = None


class DkptoSearchResponse(BaseModel):
    patents: list[DiscoverPatentResult]
    total_found: int
    source: str = "EPO Espacenet (DK)"
    error: str | None = None


DANISH_COMPANIES: list[DanishCompany] = [
    DanishCompany(name="Novo Nordisk", ticker="NOVO-B.CO", epo_names=["NOVO NORDISK"], sector="Pharma"),
    DanishCompany(name="Vestas", ticker="VWS.CO", epo_names=["VESTAS WIND SYSTEMS"], sector="Clean Energy"),
    DanishCompany(name="Orsted", ticker="ORSTED.CO", epo_names=["ORSTED"], sector="Clean Energy"),
    DanishCompany(name="Coloplast", ticker="COLO-B.CO", epo_names=["COLOPLAST"], sector="MedTech"),
    DanishCompany(name="Demant", ticker="DEMANT.CO", epo_names=["DEMANT", "WILLIAM DEMANT"], sector="MedTech"),
    DanishCompany(name="GN Store Nord", ticker="GN.CO", epo_names=["GN AUDIO", "GN HEARING"], sector="Audio/MedTech"),
    DanishCompany(name="Rockwool", ticker="ROCK-B.CO", epo_names=["ROCKWOOL"], sector="Building Materials"),
    DanishCompany(name="Novonesis", ticker="NZYM-B.CO", epo_names=["NOVOZYMES", "NOVONESIS"], sector="Biotech"),
    DanishCompany(name="Ambu", ticker="AMBU-B.CO", epo_names=["AMBU"], sector="MedTech"),
    DanishCompany(name="Bavarian Nordic", ticker="BAVA.CO", epo_names=["BAVARIAN NORDIC"], sector="Pharma"),
    DanishCompany(name="FLSmidth", ticker="FLS.CO", epo_names=["FLSMIDTH"], sector="Industrial"),
    DanishCompany(name="Genmab", ticker="GMAB.CO", epo_names=["GENMAB"], sector="Biotech"),
    DanishCompany(name="Zealand Pharma", ticker="ZEAL.CO", epo_names=["ZEALAND PHARMA"], sector="Pharma"),
    DanishCompany(name="Lundbeck", ticker="LUN.CO", epo_names=["LUNDBECK", "H LUNDBECK"], sector="Pharma"),
    DanishCompany(name="ALK-Abello", ticker="ALK-B.CO", epo_names=["ALK-ABELLO", "ALK"], sector="Pharma"),
    DanishCompany(name="Carlsberg", ticker="CARL-B.CO", epo_names=["CARLSBERG"], sector="Beverages"),
    DanishCompany(name="NKT", ticker="NKT.CO", epo_names=["NKT"], sector="Cables/Energy"),
    DanishCompany(name="Nilfisk", ticker="NLFSK.CO", epo_names=["NILFISK"], sector="Industrial"),
    DanishCompany(name="Pandora", ticker="PNDORA.CO", epo_names=["PANDORA"], sector="Consumer"),
    DanishCompany(name="DSV", ticker="DSV.CO", epo_names=["DSV"], sector="Logistics"),
]


# ---------------------------------------------------------------------------
# Ticker -> company name resolution
# ---------------------------------------------------------------------------

_TICKER_OVERRIDES: dict[str, str] = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
}

_name_cache: dict[str, str] = {}


def _clean_company_name(raw_name: str) -> str:
    """Strip common suffixes like 'A/S', 'Inc.', 'SE' for better EPO search."""
    cleaned = re.sub(
        r'\s*\b(A/S|B\s+A/S|Inc\.?|Corp\.?|Ltd\.?|SE|AG|plc|NV|SA|GmbH|Co\.?|& Co\.?|Group)\s*$',
        '', raw_name, flags=re.IGNORECASE,
    ).strip()
    cleaned = cleaned.rstrip(',. ')
    return cleaned or raw_name


def _company_name_for_ticker(ticker: str) -> str:
    """Resolve ticker to company name for patent search."""
    if ticker in _TICKER_OVERRIDES:
        return _TICKER_OVERRIDES[ticker]

    if ticker in _name_cache:
        return _name_cache[ticker]

    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        raw_name = info.get("shortName") or info.get("longName") or ticker
        name = _clean_company_name(raw_name)
        _name_cache[ticker] = name
        return name
    except Exception:
        logger.warning("Could not resolve company name for %s via yfinance", ticker)
        _name_cache[ticker] = ticker
        return ticker


# ---------------------------------------------------------------------------
# In-memory cache (10-min TTL)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 600


def _get_cached(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _set_cached(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# EPO OPS API - OAuth2 + Patent Search (per-ticker)
# ---------------------------------------------------------------------------

_EPO_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_EPO_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"
_EPO_SEARCH_BIBLIO_URL = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"

_NS = {
    "ops": "http://ops.epo.org",
    "xlink": "http://www.w3.org/1999/xlink",
    "epo": "http://www.epo.org/exchange",
}

# Namespace aliases for discovery XML parsing
_NS_DISCOVER = {
    "ops": "http://ops.epo.org",
    "ex": "http://www.epo.org/exchange",
}


def _get_epo_credentials() -> tuple[str, str] | None:
    """Get EPO OPS Consumer Key + Secret from environment."""
    key = os.environ.get("EPO_OPS_KEY")
    secret = os.environ.get("EPO_OPS_SECRET")
    if key and secret:
        return key, secret
    return None


async def _get_epo_access_token() -> str | None:
    """Get OAuth2 access token from EPO OPS (cached)."""
    cached_token = _get_cached("epo_token")
    if cached_token:
        return cached_token

    creds = _get_epo_credentials()
    if not creds:
        return None

    key, secret = creds
    auth_string = base64.b64encode(f"{key}:{secret}".encode()).decode()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _EPO_TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        _cache["epo_token"] = (time.time(), token)
        return token


def _get_epo_access_token_sync() -> str:
    """Get OAuth2 access token from EPO OPS (sync, for discovery)."""
    cached_token = _get_cached("epo_token")
    if cached_token:
        return cached_token

    creds = _get_epo_credentials()
    if not creds:
        raise ValueError("EPO_OPS_KEY and EPO_OPS_SECRET must be set")

    key, secret = creds
    resp = httpx.post(
        _EPO_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(key, secret),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["access_token"]
    _cache["epo_token"] = (time.time(), token)
    return token


def _parse_epo_search_results(xml_bytes: bytes) -> list[PatentResult]:
    """Parse EPO OPS XML search results into PatentResult list."""
    patents: list[PatentResult] = []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.warning("Failed to parse EPO XML response")
        return patents

    for doc in root.iter("{http://www.epo.org/exchange}exchange-document"):
        patent_number = ""
        title = ""
        applicant = ""
        filing_date = None
        status = doc.attrib.get("kind", "")

        country = doc.attrib.get("country", "")
        doc_number = doc.attrib.get("doc-number", "")
        kind = doc.attrib.get("kind", "")
        if country and doc_number:
            patent_number = f"{country}{doc_number}{kind}"

        for title_el in doc.iter("{http://www.epo.org/exchange}invention-title"):
            lang = title_el.attrib.get("lang", "")
            text = (title_el.text or "").strip()
            if text:
                if lang == "en" or not title:
                    title = text

        applicants = []
        for app_el in doc.iter("{http://www.epo.org/exchange}applicant"):
            data_format = app_el.attrib.get("data-format", "")
            if data_format == "epodoc":
                name_el = app_el.find("{http://www.epo.org/exchange}applicant-name/{http://www.epo.org/exchange}name")
                if name_el is not None and name_el.text:
                    applicants.append(name_el.text.strip())
        applicant = "; ".join(applicants) if applicants else ""

        for app_ref in doc.iter("{http://www.epo.org/exchange}application-reference"):
            date_el = app_ref.find("{http://www.epo.org/exchange}document-id/{http://www.epo.org/exchange}date")
            if date_el is not None and date_el.text:
                raw = date_el.text.strip()
                if len(raw) == 8:
                    filing_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
                else:
                    filing_date = raw
                break

        if patent_number:
            patents.append(PatentResult(
                patent_number=patent_number,
                title=title or "No title available",
                applicant=applicant,
                filing_date=filing_date,
                status=kind or None,
            ))

    return patents


async def search_epo_patents(company_name: str) -> tuple[list[PatentResult], str | None]:
    """Search EPO OPS API for patents by applicant name.

    Returns (patents, error_message).
    """
    cache_key = f"epo:{company_name.lower()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.info("Returning cached EPO results for %s", company_name)
        return cached, None

    if not _get_epo_credentials():
        return [], (
            "EPO OPS credentials not configured. "
            "Register for free at https://developers.epo.org/ and set "
            "EPO_OPS_KEY and EPO_OPS_SECRET in .env"
        )

    try:
        token = await _get_epo_access_token()
        if not token:
            return [], "Failed to obtain EPO OPS access token."

        cql = f'pa="{company_name}"'

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                _EPO_SEARCH_URL,
                params={"q": cql, "Range": "1-25"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/xml",
                },
            )

            if resp.status_code == 404:
                return [], None

            if resp.status_code == 403:
                _cache.pop("epo_token", None)
                token = await _get_epo_access_token()
                if not token:
                    return [], "EPO OPS authentication failed."
                resp = await client.get(
                    _EPO_SEARCH_URL,
                    params={"q": cql, "Range": "1-25"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/xml",
                    },
                )

            if resp.status_code != 200:
                return [], f"EPO OPS returned status {resp.status_code}."

            search_xml = resp.content
            root = ET.fromstring(search_xml)

            pub_refs = []
            for ref in root.iter("{http://ops.epo.org}publication-reference"):
                doc_id = ref.find("{http://www.epo.org/exchange}document-id")
                if doc_id is not None:
                    country = ""
                    doc_num = ""
                    kind = ""
                    for child in doc_id:
                        tag = child.tag.split("}")[-1]
                        if tag == "country":
                            country = (child.text or "").strip()
                        elif tag == "doc-number":
                            doc_num = (child.text or "").strip()
                        elif tag == "kind":
                            kind = (child.text or "").strip()
                    if country and doc_num:
                        pub_refs.append(f"{country}.{doc_num}.{kind}" if kind else f"{country}.{doc_num}")

            if not pub_refs:
                return [], None

            biblio_refs = ",".join(pub_refs[:20])
            biblio_url = (
                f"https://ops.epo.org/3.2/rest-services/"
                f"published-data/publication/epodoc/{biblio_refs}/biblio"
            )
            biblio_resp = await client.get(
                biblio_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/xml",
                },
            )

            if biblio_resp.status_code != 200:
                patents = []
                for ref in pub_refs[:25]:
                    parts = ref.split(".")
                    patents.append(PatentResult(
                        patent_number=ref.replace(".", ""),
                        title="(title unavailable)",
                        applicant=company_name,
                        filing_date=None,
                        status=parts[-1] if len(parts) > 2 else None,
                    ))
                _set_cached(cache_key, patents)
                return patents, None

            patents = _parse_epo_search_results(biblio_resp.content)
            patents.sort(key=lambda p: p.filing_date or "", reverse=True)
            _set_cached(cache_key, patents)
            return patents, None

    except httpx.TimeoutException:
        return [], "EPO OPS timed out. Try again in a moment."
    except Exception as e:
        logger.exception("EPO patent search failed")
        return [], f"EPO patent search failed: {str(e)}"


# ---------------------------------------------------------------------------
# Gemini 2.5 Flash AI analysis (per-ticker)
# ---------------------------------------------------------------------------

def _get_gemini_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY")


async def analyze_patents_with_gemini(
    patents: list[PatentResult],
    company_name: str,
    ticker: str,
) -> PatentAnalyzeResponse:
    """Send patent list to Gemini 2.5 Flash for investment-relevance scoring."""
    api_key = _get_gemini_api_key()
    if not api_key:
        return PatentAnalyzeResponse(
            ticker=ticker,
            company_name=company_name,
            scores=[],
            summary="Gemini API key not configured. Set GEMINI_API_KEY in .env",
            model="gemini-2.5-flash",
        )

    if not patents:
        return PatentAnalyzeResponse(
            ticker=ticker,
            company_name=company_name,
            scores=[],
            summary="No patents to analyze.",
            model="gemini-2.5-flash",
        )

    patent_text = "\n".join(
        f"- {p.patent_number}: \"{p.title}\" (applicant: {p.applicant}, "
        f"date: {p.filing_date or 'N/A'}, status: {p.status or 'N/A'})"
        for p in patents
    )

    system_prompt = (
        "You are a financial analyst specializing in patent analysis for stock investors. "
        "You evaluate patent applications and assess their potential impact on the company's "
        "stock value and competitive position.\n\n"
        "For each patent, provide:\n"
        "1. A score: POSITIVE (strengthens competitive moat, new revenue potential), "
        "INSIGNIFICANT (routine/incremental, minimal market impact), or "
        "NEGATIVE (defensive filing, potential legal issues, signals weakness)\n"
        "2. A brief reasoning (1-2 sentences) in Danish\n\n"
        "Also provide an overall summary assessment in Danish (2-3 sentences) covering "
        "the patent portfolio's impact on the investment thesis for this company.\n\n"
        "IMPORTANT: Respond in valid JSON format with this structure:\n"
        "{\n"
        '  "scores": [\n'
        '    {"patent_number": "...", "title": "...", "score": "POSITIVE|INSIGNIFICANT|NEGATIVE", "reasoning": "..."}\n'
        "  ],\n"
        '  "summary": "Overall assessment..."\n'
        "}"
    )

    user_prompt = (
        f"Company: {company_name} (ticker: {ticker})\n\n"
        f"Recent patent applications:\n{patent_text}\n\n"
        "Analyze each patent's potential impact on the company's stock value."
    )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]},
            ],
        )

        text = response.text or ""
        text = re.sub(r'^```(?:json)?\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text.strip())

        data: dict[str, Any] = json.loads(text)

        scores = [
            PatentScore(
                patent_number=s.get("patent_number", ""),
                title=s.get("title", ""),
                score=s.get("score", "INSIGNIFICANT"),
                reasoning=s.get("reasoning", ""),
            )
            for s in data.get("scores", [])
        ]

        return PatentAnalyzeResponse(
            ticker=ticker,
            company_name=company_name,
            scores=scores,
            summary=data.get("summary", "No summary available."),
            model="gemini-2.5-flash",
        )

    except ImportError:
        return PatentAnalyzeResponse(
            ticker=ticker,
            company_name=company_name,
            scores=[],
            summary="google-genai package not installed. Run: pip install google-genai",
            model="gemini-2.5-flash",
        )
    except Exception as e:
        logger.exception("Gemini analysis failed")
        return PatentAnalyzeResponse(
            ticker=ticker,
            company_name=company_name,
            scores=[],
            summary=f"AI analysis failed: {str(e)}",
            model="gemini-2.5-flash",
        )


# ===========================================================================
# Company Search / Patent Discovery (new tab)
# ===========================================================================


def _normalize_applicant(name: str) -> str:
    """Normalize applicant name: remove country codes, clean up."""
    name = re.sub(r"\s*\[.*?\]\s*$", "", name)
    name = name.strip().upper().rstrip(",.")
    return name


def _build_discovery_cql(
    query: str,
    ipc: str | None,
    date_from: str | None,
    date_to: str | None,
) -> str:
    """Build CQL query for EPO OPS discovery search."""
    parts = [f'ti="{query}" OR ab="{query}"']
    if ipc:
        parts.append(f'ic="{ipc}"')

    if not date_from and not date_to:
        current_year = time.strftime("%Y")
        date_from = str(int(current_year) - 2)
        date_to = current_year

    if date_from and date_to:
        parts.append(f'pd within "{date_from} {date_to}"')
    elif date_from:
        parts.append(f'pd >= "{date_from}"')
    elif date_to:
        parts.append(f'pd <= "{date_to}"')

    return " AND ".join(parts)


def _parse_discovery_biblio_xml(xml_text: str) -> list[DiscoverPatentResult]:
    """Parse EPO OPS biblio XML into DiscoverPatentResult list."""
    patents: list[DiscoverPatentResult] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.error("Failed to parse EPO XML response")
        return patents

    for doc in root.findall(".//ex:exchange-document", _NS_DISCOVER):
        title = ""
        for inv_title in doc.findall(".//ex:invention-title", _NS_DISCOVER):
            lang = inv_title.get("lang", "")
            text = (inv_title.text or "").strip()
            if lang == "en" and text:
                title = text
                break
            if not title and text:
                title = text

        country = doc.get("country", "")
        doc_number = doc.get("doc-number", "")
        kind = doc.get("kind", "")
        patent_number = f"{country}{doc_number}{kind}" if doc_number else ""

        date = ""
        date_el = doc.find(
            ".//ex:publication-reference"
            "//ex:document-id[@document-id-type='docdb']"
            "//ex:date",
            _NS_DISCOVER,
        )
        if date_el is not None and date_el.text:
            raw = date_el.text.strip()
            if len(raw) == 8:
                date = f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
            else:
                date = raw

        applicant = ""
        for app_el in doc.findall(".//ex:applicants/ex:applicant", _NS_DISCOVER):
            name_el = app_el.find(".//ex:name", _NS_DISCOVER)
            if name_el is not None and name_el.text:
                applicant = _normalize_applicant(name_el.text)
                break

        if title and applicant:
            patents.append(
                DiscoverPatentResult(
                    title=title,
                    patent_number=patent_number,
                    date=date or None,
                    applicant=applicant,
                )
            )

    return patents


def discover_patents(request: DiscoverRequest) -> DiscoverResponse:
    """Search EPO OPS by keyword and group results by company."""
    try:
        token = _get_epo_access_token_sync()
        cql = _build_discovery_cql(
            request.query, request.ipc, request.date_from, request.date_to
        )
        logger.info("EPO discovery CQL: %s", cql)

        all_patents: list[DiscoverPatentResult] = []
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/xml",
        }

        for start in range(1, 101, 25):
            end = start + 24
            try:
                resp = httpx.get(
                    _EPO_SEARCH_BIBLIO_URL,
                    params={"q": cql, "Range": f"{start}-{end}"},
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code == 404:
                    break
                if resp.status_code == 403:
                    _cache.pop("epo_token", None)
                    token = _get_epo_access_token_sync()
                    headers["Authorization"] = f"Bearer {token}"
                    resp = httpx.get(
                        _EPO_SEARCH_BIBLIO_URL,
                        params={"q": cql, "Range": f"{start}-{end}"},
                        headers=headers,
                        timeout=30,
                    )
                resp.raise_for_status()
                batch = _parse_discovery_biblio_xml(resp.text)
                all_patents.extend(batch)
                if len(batch) < 25:
                    break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break
                logger.warning("EPO batch %d-%d failed: %s", start, end, e)
                break

        if not all_patents:
            return DiscoverResponse(
                query=request.query,
                companies=[],
                total_patents=0,
                error="Ingen patenter fundet. Proev andre soegeord eller bredere datointerval.",
            )

        groups: dict[str, list[DiscoverPatentResult]] = defaultdict(list)
        for p in all_patents:
            groups[p.applicant].append(p)

        sorted_companies = sorted(
            groups.items(), key=lambda x: len(x[1]), reverse=True
        )[:15]

        companies = [
            CompanyPatents(
                company=company,
                patent_count=len(patents),
                sample_patents=patents[:5],
            )
            for company, patents in sorted_companies
        ]

        return DiscoverResponse(
            query=request.query,
            companies=companies,
            total_patents=len(all_patents),
        )
    except Exception as e:
        logger.exception("Patent discovery failed")
        return DiscoverResponse(
            query=request.query,
            companies=[],
            total_patents=0,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Gemini AI analysis for discovery
# ---------------------------------------------------------------------------

_GEMINI_REST_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def analyze_discovery_with_gemini(
    request: DiscoverAnalyzeRequest,
) -> DiscoverAnalyzeResponse:
    """Use Gemini to rank discovered companies for investment potential."""
    api_key = _get_gemini_api_key()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        raise ValueError("GEMINI_API_KEY must be set")

    company_lines = []
    for c in request.companies:
        titles = "; ".join(p.title for p in c.sample_patents[:5])
        company_lines.append(f"- {c.company} ({c.patent_count} patents): {titles}")
    companies_text = "\n".join(company_lines)

    system_prompt = (
        "Du er en investeringsanalytiker. Evaluer disse virksomheder baseret pa deres "
        f"nylige patentaktivitet inden for '{request.query}'. "
        "Ranger dem efter investeringspotentiale.\n\n"
        "Returner JSON med denne struktur:\n"
        '{"rankings": [{"company": "NAME", "score": "STRONG BUY|INTERESTING|NEUTRAL|WEAK", '
        '"reasoning": "kort begrundelse pa dansk", "patent_count": N}], '
        '"summary": "overordnet investerings-opsummering pa dansk"}\n\n'
        "Score-skala:\n"
        "- STRONG BUY: Klar teknologileder med staerk patentportefolje\n"
        "- INTERESTING: Lovende patentaktivitet, vaerd at undersoge naermere\n"
        "- NEUTRAL: Gennemsnitlig patentaktivitet\n"
        "- WEAK: Begraenset eller uinteressant patentaktivitet\n\n"
        "Al reasoning og summary SKAL vaere pa dansk."
    )

    user_prompt = (
        f"Teknologiomrade: {request.query}\n\n"
        f"Virksomheder og deres patenter:\n{companies_text}"
    )

    url = _GEMINI_REST_URL.format(model=model)
    resp = httpx.post(
        f"{url}?key={api_key}",
        json={
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "rankings": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "company": {"type": "string"},
                                    "score": {"type": "string"},
                                    "reasoning": {"type": "string"},
                                    "patent_count": {"type": "integer"},
                                },
                                "required": [
                                    "company",
                                    "score",
                                    "reasoning",
                                    "patent_count",
                                ],
                            },
                        },
                        "summary": {"type": "string"},
                    },
                    "required": ["rankings", "summary"],
                },
            },
        },
        timeout=60,
    )
    resp.raise_for_status()

    result_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    result = json.loads(result_text)

    rankings = [
        CompanyRanking(
            company=r["company"],
            score=r["score"],
            reasoning=r["reasoning"],
            patent_count=r["patent_count"],
        )
        for r in result.get("rankings", [])
    ]

    return DiscoverAnalyzeResponse(
        query=request.query,
        rankings=rankings,
        summary=result.get("summary", ""),
        model=model,
    )


# ===========================================================================
# Stars - Danish Patent Screener
# ===========================================================================

_stars_cache: dict[str, tuple[float, Any]] = {}
_STARS_CACHE_TTL = 3600  # 1 hour

_STARS_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STARS_LATEST_FILE = _STARS_DATA_DIR / "stars_latest.json"

# Baseline window for area-shift detection (days before the scan window)
_SHIFT_BASELINE_DAYS = 365
# Minimum sample sizes before a shift is flagged
_SHIFT_MIN_RECENT = 3
_SHIFT_MIN_BASELINE = 5
_SHIFT_THRESHOLD = 0.4


_epo_throttle = {"interval": 1.0, "last": 0.0}
_epo_throttle_lock = threading.Lock()


def _epo_wait() -> None:
    """Space EPO search calls according to the last X-Throttling-Control header."""
    with _epo_throttle_lock:
        wait = _epo_throttle["last"] + _epo_throttle["interval"] - time.time()
        if wait > 0:
            time.sleep(wait)
        _epo_throttle["last"] = time.time()


def _update_epo_throttle(resp: httpx.Response) -> None:
    # e.g. "busy (images=green:100, ..., search=yellow:5)" - number is requests/minute
    m = re.search(r"search=(\w+):(\d+)", resp.headers.get("X-Throttling-Control", ""))
    if not m:
        return
    color, per_minute = m.group(1), int(m.group(2))
    interval = 60 / max(per_minute, 1)
    if color in ("red", "black"):
        interval = max(interval, 30)
    _epo_throttle["interval"] = max(0.5, interval)


def _epo_get(params: dict[str, str]) -> httpx.Response | None:
    """GET the EPO biblio search with throttling and retries. None = gave up."""
    token_refreshed = False
    for attempt in range(5):
        _epo_wait()
        try:
            resp = httpx.get(
                _EPO_SEARCH_BIBLIO_URL,
                params=params,
                headers={"Authorization": f"Bearer {_get_epo_access_token_sync()}", "Accept": "application/xml"},
                timeout=30,
            )
        except httpx.HTTPError as e:
            logger.warning("EPO request error (attempt %d): %s", attempt + 1, e)
            time.sleep(5 * (attempt + 1))
            continue
        _update_epo_throttle(resp)
        if resp.status_code in (200, 404):  # 404 = no results
            return resp
        rejection = resp.headers.get("X-Rejection-Reason", "")
        if resp.status_code in (400, 401, 403) and not token_refreshed and "throttl" not in rejection.lower():
            _cache.pop("epo_token", None)
            token_refreshed = True
            continue
        if resp.status_code in (403, 429, 500, 502, 503, 504):
            retry_after = resp.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else (10, 30, 60, 90, 120)[attempt]
            logger.info("EPO %s (%s), retrying in %.0fs", resp.status_code, rejection or "-", delay)
            time.sleep(delay)
            continue
        logger.warning("EPO search failed: HTTP %s %s", resp.status_code, resp.text[:200])
        return None
    return None


def _format_epo_date(raw: str) -> str:
    raw = raw.strip()
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}" if len(raw) == 8 else raw


def _parse_stars_hits(root: ET.Element, default_applicant: str) -> list[StarsPatentHit]:
    hits: list[StarsPatentHit] = []
    for doc in root.findall(".//ex:exchange-document", _NS_DISCOVER):
        title = ""
        for inv_title in doc.findall(".//ex:invention-title", _NS_DISCOVER):
            lang = inv_title.get("lang", "")
            text = (inv_title.text or "").strip()
            if lang == "en" and text:
                title = text
                break
            if not title and text:
                title = text

        country = doc.get("country", "")
        doc_number = doc.get("doc-number", "")
        kind = doc.get("kind", "")
        patent_number = f"{country}{doc_number}{kind}" if doc_number else ""

        filing_date = None
        for app_ref in doc.findall(".//ex:application-reference", _NS_DISCOVER):
            date_el = app_ref.find(".//ex:date", _NS_DISCOVER)
            if date_el is not None and date_el.text:
                filing_date = _format_epo_date(date_el.text)
                break

        pub_date = None
        pub_ref = doc.find(".//ex:publication-reference", _NS_DISCOVER)
        if pub_ref is not None:
            pd_el = pub_ref.find(".//ex:date", _NS_DISCOVER)
            if pd_el is not None and pd_el.text:
                pub_date = _format_epo_date(pd_el.text)

        # Prefer the normalised Latin "epodoc" names; "original" ones may be in CJK scripts
        app_els = doc.findall(".//ex:applicants/ex:applicant", _NS_DISCOVER)
        epodoc = [a for a in app_els if a.get("data-format") == "epodoc"]
        applicants: list[str] = []
        for app_el in epodoc or app_els:
            name_el = app_el.find(".//ex:name", _NS_DISCOVER)
            if name_el is not None and name_el.text:
                name = _normalize_applicant(name_el.text)
                if name and name not in applicants:
                    applicants.append(name)

        ipc: list[str] = []
        for ipc_el in doc.findall(".//ex:classifications-ipcr/ex:classification-ipcr/ex:text", _NS_DISCOVER):
            subclass = (ipc_el.text or "").replace(" ", "")[:4]
            if len(subclass) == 4 and subclass not in ipc:
                ipc.append(subclass)

        if patent_number and title:
            hits.append(StarsPatentHit(
                patent_number=patent_number,
                title=title,
                applicant=applicants[0] if applicants else default_applicant,
                applicants=applicants,
                filing_date=filing_date,
                publication_date=pub_date,
                ipc=ipc,
            ))
    return hits


def epo_applicant_search(
    epo_name: str,
    date_from: str,
    date_to: str,
    max_results: int = 25,
) -> tuple[list[StarsPatentHit], int] | None:
    """Search EPO OPS by applicant within a publication-date range.

    Returns (hits, total_result_count), or None if EPO could not be queried.
    """
    cql = f'pa="{epo_name}" AND pd within "{date_from} {date_to}"'
    hits: list[StarsPatentHit] = []
    total = 0
    for first in range(1, max_results + 1, 100):  # EPO pages are at most 100
        last = min(first + 99, max_results)
        resp = _epo_get({"q": cql, "Range": f"{first}-{last}"})
        if resp is None:
            return None
        if resp.status_code == 404:
            break
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return None
        search_el = root.find(".//ops:biblio-search", _NS_DISCOVER)
        total = int(search_el.get("total-result-count", "0")) if search_el is not None else 0
        hits.extend(_parse_stars_hits(root, epo_name))
        if last >= total:
            break
    return hits, total


def _search_epo_patents_sync(
    epo_name: str,
    date_from: str,
    date_to: str,
    max_results: int = 25,
) -> list[StarsPatentHit] | None:
    """Search EPO OPS for patents by applicant name within date range. None = failed."""
    result = epo_applicant_search(epo_name, date_from, date_to, max_results)
    if result is None:
        logger.warning("Stars EPO search failed for %s (%s-%s)", epo_name, date_from, date_to)
        return None
    return result[0]


def _enrich_stock_prices(results: list[CompanyStarsResult]) -> None:
    """Add stock price and daily change to each company result."""
    from concurrent.futures import ThreadPoolExecutor

    import yfinance as yf

    def _fetch_price(result: CompanyStarsResult) -> None:
        try:
            info = yf.Ticker(result.ticker).info
            result.stock_price = info.get("regularMarketPrice") or info.get("currentPrice")
            change = info.get("regularMarketChangePercent")
            if change is not None:
                result.stock_change_pct = round(change, 2)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=5) as pool:
        pool.map(_fetch_price, results)


def _score_companies_with_gemini(
    results: list[CompanyStarsResult],
) -> tuple[str, str]:
    """Score all companies with a single Gemini call. Returns (summary, model)."""
    api_key = _get_gemini_api_key()
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        return "Gemini API key not configured.", model

    companies_with_patents = [r for r in results if r.patent_count > 0]
    if not companies_with_patents:
        return "Ingen patenter fundet i perioden.", model

    company_lines = []
    for r in companies_with_patents:
        titles = "; ".join(p.title for p in r.recent_patents[:5])
        company_lines.append(
            f"- {r.name} ({r.ticker}, {r.sector}, {r.patent_count} patenter): {titles}"
        )
    companies_text = "\n".join(company_lines)

    system_prompt = (
        "Du er en dansk investeringsanalytiker der specialiserer sig i patentanalyse for "
        "OMX Copenhagen-noterede virksomheder. Evaluer disse virksomheders nylige "
        "patentaktivitet og ranger dem efter investeringspotentiale.\n\n"
        "For HVER virksomhed med patenter, giv:\n"
        "- stars: 1-5 (5 = exceptionel innovationsaktivitet, 1 = minimal)\n"
        "- signal: STRONG/MODERATE/WEAK/NONE\n"
        "- summary: kort begrundelse pa dansk (1-2 saetninger)\n\n"
        "Giv ogsa en overordnet markedsopsummering pa dansk.\n\n"
        "Returner JSON:\n"
        '{"companies": [{"name": "...", "stars": N, "signal": "...", "summary": "..."}], '
        '"market_summary": "..."}'
    )

    user_prompt = f"Danske virksomheder og deres nylige patenter:\n{companies_text}"

    url = _GEMINI_REST_URL.format(model=model)
    try:
        resp = httpx.post(
            f"{url}?key={api_key}",
            json={
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "object",
                        "properties": {
                            "companies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "stars": {"type": "integer"},
                                        "signal": {"type": "string"},
                                        "summary": {"type": "string"},
                                    },
                                    "required": ["name", "stars", "signal", "summary"],
                                },
                            },
                            "market_summary": {"type": "string"},
                        },
                        "required": ["companies", "market_summary"],
                    },
                },
            },
            timeout=90,
        )
        resp.raise_for_status()
        result_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(result_text)

        # Map scores back to results
        score_map = {c["name"].lower(): c for c in data.get("companies", [])}
        for r in results:
            match = score_map.get(r.name.lower())
            if match:
                r.stars = max(1, min(5, match.get("stars", 0)))
                r.ai_signal = match.get("signal", "NONE")
                r.ai_summary = match.get("summary", "")

        return data.get("market_summary", ""), model
    except Exception as e:
        logger.exception("Stars Gemini scoring failed")
        return f"AI-scoring fejlede: {e}", model


def _search_company_sync(
    company: DanishCompany,
    date_from: str,
    date_to: str,
    max_results: int = 25,
) -> tuple[list[StarsPatentHit], bool]:
    """Search all EPO applicant names for a company, deduplicated by patent number.

    Returns (hits, complete) - complete is False if any lookup failed.
    """
    seen: set[str] = set()
    unique_hits: list[StarsPatentHit] = []
    complete = True
    for epo_name in company.epo_names:
        hits = _search_epo_patents_sync(epo_name, date_from, date_to, max_results)
        if hits is None:
            complete = False
            continue
        for h in hits:
            if h.patent_number not in seen:
                seen.add(h.patent_number)
                unique_hits.append(h)
    return unique_hits, complete


def _share(counts: dict[str, float]) -> dict[str, float]:
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()} if total else {}


def _tvd(a: dict[str, float], b: dict[str, float]) -> float:
    """Total variation distance between two distributions (0 = identical, 1 = disjoint)."""
    keys = set(a) | set(b)
    return round(0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys), 3)


def _ipc_counts(hits: list[StarsPatentHit]) -> dict[str, float]:
    # Each patent contributes weight 1, split across its IPC subclasses
    counts: dict[str, float] = defaultdict(float)
    for h in hits:
        for c in h.ipc:
            counts[c] += 1 / len(h.ipc)
    return counts


def _office_counts(hits: list[StarsPatentHit]) -> dict[str, float]:
    counts: dict[str, float] = defaultdict(float)
    for h in hits:
        office = h.patent_number[:2]
        if office.isalpha():
            counts[office] += 1
    return counts


def _top(counts: dict[str, float], n: int = 3) -> list[str]:
    return [k for k, _ in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]]


def compute_area_shift(
    recent: list[StarsPatentHit],
    baseline: list[StarsPatentHit],
    data_complete: bool = True,
) -> AreaShift:
    """Compare technology (IPC) and filing-office mix of recent vs. baseline patents."""
    ipc_recent, ipc_base = _ipc_counts(recent), _ipc_counts(baseline)
    off_recent, off_base = _office_counts(recent), _office_counts(baseline)
    enough = len(recent) >= _SHIFT_MIN_RECENT and len(baseline) >= _SHIFT_MIN_BASELINE

    ipc_shift = _tvd(_share(ipc_recent), _share(ipc_base)) if enough and ipc_recent and ipc_base else None
    office_shift = _tvd(_share(off_recent), _share(off_base)) if enough and off_recent and off_base else None
    new_ipc = [c for c in _top(ipc_recent, 10) if c not in ipc_base] if baseline else []
    new_offices = [o for o in _top(off_recent, 10) if o not in off_base] if baseline else []

    return AreaShift(
        baseline_count=len(baseline),
        recent_count=len(recent),
        ipc_shift=ipc_shift,
        office_shift=office_shift,
        new_ipc=new_ipc,
        new_offices=new_offices,
        top_ipc_recent=_top(ipc_recent),
        top_ipc_baseline=_top(ipc_base),
        flagged=data_complete and any(x is not None and x >= _SHIFT_THRESHOLD for x in (ipc_shift, office_shift)),
        data_complete=data_complete,
    )


def _save_latest_scan(response: StarsScanResponse) -> None:
    try:
        _STARS_DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STARS_LATEST_FILE.with_suffix(".tmp")
        tmp.write_text(response.model_dump_json(indent=2))
        tmp.replace(_STARS_LATEST_FILE)
    except OSError:
        logger.exception("Could not persist Stars scan")


def load_latest_scan() -> StarsScanResponse | None:
    """Return the most recently persisted Stars scan (manual or scheduled)."""
    if not _STARS_LATEST_FILE.exists():
        return None
    try:
        return StarsScanResponse.model_validate_json(_STARS_LATEST_FILE.read_text())
    except Exception:
        logger.exception("Could not read persisted Stars scan")
        return None


def run_stars_scan(
    period_days: int = 90,
    trigger: str = "manual",
    use_cache: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> StarsScanResponse:
    """Run a full Stars scan of Danish companies.

    progress(step, total, message) is called as companies are processed.
    """
    import datetime

    cache_key = f"stars:{period_days}"
    cached = _stars_cache.get(cache_key)
    if use_cache and cached and (time.time() - cached[0]) < _STARS_CACHE_TTL:
        return cached[1]

    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=period_days)
    date_from = window_start.strftime("%Y%m%d")
    date_to = today.strftime("%Y%m%d")
    base_from = (window_start - datetime.timedelta(days=_SHIFT_BASELINE_DAYS)).strftime("%Y%m%d")
    base_to = (window_start - datetime.timedelta(days=1)).strftime("%Y%m%d")

    results: list[CompanyStarsResult] = []
    total_patents = 0

    n_steps = len(DANISH_COMPANIES) + 2
    for i, company in enumerate(DANISH_COMPANIES):
        if progress:
            progress(i, n_steps, f"Fetching patents: {company.name}")
        unique_hits, recent_ok = _search_company_sync(company, date_from, date_to)
        baseline_hits, base_ok = _search_company_sync(company, base_from, base_to, max_results=100)

        total_patents += len(unique_hits)
        results.append(CompanyStarsResult(
            name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            patent_count=len(unique_hits),
            recent_patents=unique_hits[:10],
            area_shift=compute_area_shift(unique_hits, baseline_hits, recent_ok and base_ok),
        ))

    # AI scoring (single consolidated call)
    if progress:
        progress(len(DANISH_COMPANIES), n_steps, "AI scoring with Gemini")
    summary, model = _score_companies_with_gemini(results)

    # Enrich with stock prices
    if progress:
        progress(len(DANISH_COMPANIES) + 1, n_steps, "Fetching share prices")
    _enrich_stock_prices(results)

    # Sort by stars (desc), then patent count
    results.sort(key=lambda r: (r.stars or 0, r.patent_count), reverse=True)

    response = StarsScanResponse(
        scan_date=today.isoformat(),
        period_days=period_days,
        companies=results,
        total_patents=total_patents,
        summary=summary,
        model=model,
        run_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        trigger=trigger,
    )

    _stars_cache[cache_key] = (time.time(), response)
    _save_latest_scan(response)

    from .alerts import notify_stars  # local import: alerts depends on this module's models
    notify_stars(response)
    return response


# ===========================================================================
# DKPTO - Danish Patent Search (via EPO with pn=DK* filter)
# ===========================================================================


def _build_dkpto_cql(request: DkptoSearchRequest) -> str:
    """Build CQL query for Danish patents via EPO OPS."""
    parts = ['pn=DK*']

    if request.applicant:
        parts.append(f'pa="{request.applicant}"')
    if request.title:
        parts.append(f'ti="{request.title}"')
    if request.ipc:
        parts.append(f'ic="{request.ipc}"')

    date_from = request.date_from
    date_to = request.date_to
    if not date_from and not date_to:
        current_year = time.strftime("%Y")
        date_from = str(int(current_year) - 2)
        date_to = current_year

    if date_from and date_to:
        parts.append(f'pd within "{date_from} {date_to}"')
    elif date_from:
        parts.append(f'pd >= "{date_from}"')
    elif date_to:
        parts.append(f'pd <= "{date_to}"')

    return " AND ".join(parts)


def search_dkpto_patents(request: DkptoSearchRequest) -> DkptoSearchResponse:
    """Search EPO OPS for Danish patents (pn=DK*)."""
    try:
        token = _get_epo_access_token_sync()
        cql = _build_dkpto_cql(request)
        logger.info("DKPTO CQL: %s", cql)

        all_patents: list[DiscoverPatentResult] = []
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/xml",
        }

        for start in range(1, 101, 25):
            end = start + 24
            try:
                resp = httpx.get(
                    _EPO_SEARCH_BIBLIO_URL,
                    params={"q": cql, "Range": f"{start}-{end}"},
                    headers=headers,
                    timeout=30,
                )
                if resp.status_code == 404:
                    break
                if resp.status_code == 403:
                    _cache.pop("epo_token", None)
                    token = _get_epo_access_token_sync()
                    headers["Authorization"] = f"Bearer {token}"
                    resp = httpx.get(
                        _EPO_SEARCH_BIBLIO_URL,
                        params={"q": cql, "Range": f"{start}-{end}"},
                        headers=headers,
                        timeout=30,
                    )
                resp.raise_for_status()
                batch = _parse_discovery_biblio_xml(resp.text)
                all_patents.extend(batch)
                if len(batch) < 25:
                    break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break
                logger.warning("DKPTO batch %d-%d failed: %s", start, end, e)
                break

        if not all_patents:
            return DkptoSearchResponse(
                patents=[],
                total_found=0,
                error="Ingen danske patenter fundet. Proev andre soegekriterier.",
            )

        # Sort by date descending
        all_patents.sort(key=lambda p: p.date or "", reverse=True)

        return DkptoSearchResponse(
            patents=all_patents,
            total_found=len(all_patents),
        )
    except Exception as e:
        logger.exception("DKPTO search failed")
        return DkptoSearchResponse(
            patents=[],
            total_found=0,
            error=str(e),
        )
