"""
agents/tools.py — Task 2: Paper search using Semantic Scholar API.

Semantic Scholar is free, requires no API key for basic use,
and does not IP-ban like arXiv does.

Falls back to arXiv if Semantic Scholar returns no results.
API docs: https://api.semanticscholar.org/api-docs/
"""
import time
import xml.etree.ElementTree as ET
import requests

from config import cfg

HEADERS = {
    "User-Agent": "MultiAgentResearchAssistant/1.0 (research tool; python-requests)"
}

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV_URL            = "https://export.arxiv.org/api/query"


def search_arxiv(query: str, max_results: int = None) -> list[dict]:
    """
    Search for academic papers. Tries Semantic Scholar first,
    falls back to arXiv if needed.

    Named search_arxiv for backwards compatibility with the rest
    of the codebase — it now searches both sources.
    """
    if max_results is None:
        max_results = cfg.MAX_PAPERS

    # Try Semantic Scholar first
    papers = _search_semantic_scholar(query, max_results)
    if papers:
        print(f"[Semantic Scholar] Found {len(papers)} papers")
        return papers

    # Fall back to arXiv
    print("[Semantic Scholar] No results — trying arXiv...")
    return _search_arxiv_fallback(query, max_results)


def _search_semantic_scholar(query: str, max_results: int) -> list[dict]:
    """Query the Semantic Scholar Graph API."""
    params = {
        "query":  query,
        "limit":  min(max_results * 2, 20),
        "fields": "title,abstract,authors,year,externalIds,citationCount",
    }

    try:
        resp = requests.get(
            SEMANTIC_SCHOLAR_URL,
            params=params,
            headers=HEADERS,
            timeout=30,
        )

        if resp.status_code == 429:
            print("[Semantic Scholar] Rate limited — waiting 10s...")
            time.sleep(10)
            resp = requests.get(
                SEMANTIC_SCHOLAR_URL,
                params=params,
                headers=HEADERS,
                timeout=30,
            )

        resp.raise_for_status()
        data = resp.json()

    except requests.RequestException as exc:
        print(f"[Semantic Scholar] Request failed: {exc}")
        return []

    papers = []
    for item in data.get("data", []):
        abstract = item.get("abstract") or ""
        if not abstract.strip():
            continue

        # Build URL from external IDs
        ext = item.get("externalIds") or {}
        if ext.get("ArXiv"):
            url = f"https://arxiv.org/abs/{ext['ArXiv']}"
        elif ext.get("DOI"):
            url = f"https://doi.org/{ext['DOI']}"
        else:
            pid = item.get("paperId", "")
            url = f"https://www.semanticscholar.org/paper/{pid}"

        authors = [
            a.get("name", "")
            for a in (item.get("authors") or [])
            if a.get("name")
        ]

        papers.append({
            "title":     item.get("title", "Untitled"),
            "authors":   authors,
            "year":      item.get("year") or 0,
            "abstract":  abstract.strip(),
            "url":       url,
            "citations": item.get("citationCount") or 0,
        })

    # Sort by citation count — more cited = more established
    papers.sort(key=lambda x: x.get("citations", 0), reverse=True)
    return papers[:max_results]


def _search_arxiv_fallback(query: str, max_results: int) -> list[dict]:
    """Fall back to arXiv with retry logic."""
    params = {
        "search_query": f"all:{query}",
        "start":        0,
        "max_results":  min(max_results * 2, 20),
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }

    for attempt in range(3):
        if attempt > 0:
            wait = 20 * attempt
            print(f"[arXiv] Waiting {wait}s before retry {attempt}/2...")
            time.sleep(wait)

        try:
            resp = requests.get(
                ARXIV_URL,
                params=params,
                headers=HEADERS,
                timeout=40,
            )
            if resp.status_code == 429:
                print(f"[arXiv] Rate limited on attempt {attempt+1}")
                continue
            resp.raise_for_status()
            papers = _parse_arxiv(resp.text)
            time.sleep(3)
            return papers[:max_results]

        except requests.Timeout:
            print(f"[arXiv] Timeout on attempt {attempt+1}")
        except requests.RequestException as exc:
            print(f"[arXiv] Failed: {exc}")

    return []


def _parse_arxiv(xml_text: str) -> list[dict]:
    """Parse arXiv Atom XML into paper dicts."""
    ns   = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    papers = []

    for entry in root.findall("atom:entry", ns):
        t = entry.find("atom:title",     ns)
        s = entry.find("atom:summary",   ns)
        i = entry.find("atom:id",        ns)
        p = entry.find("atom:published", ns)

        title    = t.text.strip().replace("\n", " ") if t else "Untitled"
        abstract = s.text.strip()                    if s else ""
        url      = i.text.strip()                    if i else ""
        year     = int(p.text[:4])                   if p else 0
        authors  = [
            n.text.strip()
            for a in entry.findall("atom:author", ns)
            if (n := a.find("atom:name", ns)) is not None
        ]

        if abstract:
            papers.append({
                "title":   title,
                "authors": authors,
                "year":    year,
                "abstract": abstract,
                "url":     url,
            })

    return papers