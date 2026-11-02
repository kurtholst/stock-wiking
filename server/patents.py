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
import time
from collections import defaultdict
from typing import Any
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


class StarsScanRequest(BaseModel):
    period_days: int = 90


class StarsScanResponse(BaseModel):
    scan_date: str
    period_days: int
    companies: list[CompanyStarsResult]
    total_patents: int
    summary: str
    model: str


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


def _search_epo_patents_sync(
    epo_name: str,
    date_from: str,
    date_to: str,
) -> list[StarsPatentHit]:
    """Search EPO OPS for patents by applicant name within date range (sync)."""
    token = _get_epo_access_token_sync()
    cql = f'pa="{epo_name}" AND pd within "{date_from} {date_to}"'
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/xml",
    }

    try:
        resp = httpx.get(
            _EPO_SEARCH_BIBLIO_URL,
            params={"q": cql, "Range": "1-25"},
            headers=headers,
            timeout=20,
        )
        if resp.status_code == 404:
            return []
        if resp.status_code == 403:
            _cache.pop("epo_token", None)
            token = _get_epo_access_token_sync()
            headers["Authorization"] = f"Bearer {token}"
            resp = httpx.get(
                _EPO_SEARCH_BIBLIO_URL,
                params={"q": cql, "Range": "1-25"},
                headers=headers,
                timeout=20,
            )
        if resp.status_code != 200:
            return []

        hits: list[StarsPatentHit] = []
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return []

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
                    raw = date_el.text.strip()
                    filing_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}" if len(raw) == 8 else raw
                    break

            pub_date = None
            pub_ref = doc.find(".//ex:publication-reference", _NS_DISCOVER)
            if pub_ref is not None:
                pd_el = pub_ref.find(".//ex:date", _NS_DISCOVER)
                if pd_el is not None and pd_el.text:
                    raw = pd_el.text.strip()
                    pub_date = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}" if len(raw) == 8 else raw

            applicant = ""
            for app_el in doc.findall(".//ex:applicants/ex:applicant", _NS_DISCOVER):
                name_el = app_el.find(".//ex:name", _NS_DISCOVER)
                if name_el is not None and name_el.text:
                    applicant = _normalize_applicant(name_el.text)
                    break

            if patent_number and title:
                hits.append(StarsPatentHit(
                    patent_number=patent_number,
                    title=title,
                    applicant=applicant or epo_name,
                    filing_date=filing_date,
                    publication_date=pub_date,
                ))

        return hits
    except Exception as e:
        logger.warning("Stars EPO search failed for %s: %s", epo_name, e)
        return []


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


def run_stars_scan(period_days: int = 90) -> StarsScanResponse:
    """Run a full Stars scan of Danish companies."""
    import datetime

    cache_key = f"stars:{period_days}"
    cached = _stars_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _STARS_CACHE_TTL:
        return cached[1]

    today = datetime.date.today()
    date_from = (today - datetime.timedelta(days=period_days)).strftime("%Y%m%d")
    date_to = today.strftime("%Y%m%d")

    results: list[CompanyStarsResult] = []
    total_patents = 0

    for company in DANISH_COMPANIES:
        all_hits: list[StarsPatentHit] = []
        for epo_name in company.epo_names:
            hits = _search_epo_patents_sync(epo_name, date_from, date_to)
            all_hits.extend(hits)
            time.sleep(0.5)  # Rate limiting

        # Deduplicate by patent_number
        seen: set[str] = set()
        unique_hits: list[StarsPatentHit] = []
        for h in all_hits:
            if h.patent_number not in seen:
                seen.add(h.patent_number)
                unique_hits.append(h)

        total_patents += len(unique_hits)
        results.append(CompanyStarsResult(
            name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            patent_count=len(unique_hits),
            recent_patents=unique_hits[:10],
        ))

    # AI scoring (single consolidated call)
    summary, model = _score_companies_with_gemini(results)

    # Enrich with stock prices
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
    )

    _stars_cache[cache_key] = (time.time(), response)
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
