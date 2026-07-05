"""Scraper publications eJustice (Moniteur belge)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape

import requests

EJUSTICE_BASE = "https://www.ejustice.just.fgov.be"


def _bce_nodot(bce: str) -> str:
    return bce.replace(".", "").replace(" ", "")


def _normalize_bce(bce: str) -> str:
    raw = _bce_nodot(bce)
    if len(raw) == 10:
        return f"{raw[:4]}.{raw[4:7]}.{raw[7:]}"
    return bce


def ejustice_list_url(bce: str, language: str = "fr", page: int = 1) -> str:
    return (
        f"{EJUSTICE_BASE}/cgi_tsv/list.pl"
        f"?language={language}&btw={_bce_nodot(bce)}&page={page}"
    )


def parse_ejustice_list_html(html: str, bce: str) -> list[dict]:
    """Extrait publications depuis la page list.pl."""
    seen: set[str] = set()
    publications: list[dict] = []

    for match in re.finditer(
        r"/tsv_pdf/(\d{4})/(\d{2})/(\d{2})/([^\"']+\.pdf)",
        html,
        re.I,
    ):
        y, mo, d, fname = match.groups()
        pdf_path = f"/tsv_pdf/{y}/{mo}/{d}/{fname}"
        if pdf_path in seen:
            continue
        seen.add(pdf_path)

        start = max(0, match.start() - 500)
        snippet = html[start : match.start()]
        titles = [
            unescape(t).strip()
            for t in re.findall(r">([^<]{4,120})<", snippet)
            if t.strip() and not t.strip().startswith("&")
        ]
        titre = ""
        for t in reversed(titles):
            upper = t.upper()
            if any(
                kw in upper
                for kw in (
                    "DEMISSION",
                    "NOMINATION",
                    "ONTSLAG",
                    "BENOEM",
                    "CAPITAL",
                    "KAPITAAL",
                    "FUSION",
                    "DISSOLUTION",
                    "STATUT",
                    "SIEG",
                    "ACTION",
                    "AANDEL",
                    "MODIFICATION",
                    "WIJZIG",
                )
            ):
                titre = re.sub(r"\s+", " ", t).strip()
                break
        if not titre:
            titre = next((t for t in reversed(titles) if len(t) > 8), "Publication Moniteur belge")

        ref_match = re.search(r"(\d{4}-\d{2}-\d{2})\s*/\s*(\d+)", snippet)
        reference = ref_match.group(2) if ref_match else fname.replace(".pdf", "")

        publications.append(
            {
                "id": f"{y}{mo}{d}-{reference}",
                "date": f"{y}-{mo}-{d}",
                "titre": titre,
                "reference": reference,
                "pdf_url": f"{EJUSTICE_BASE}{pdf_path}",
                "liste_url": ejustice_list_url(bce),
                "source": "ejustice",
            }
        )

    publications.sort(key=lambda p: p["date"], reverse=True)
    return publications


def fetch_ejustice_publications(bce: str, cfg: dict, max_pages: int = 2) -> list[dict]:
    language = cfg.get("ejustice", {}).get("language", "fr")
    headers = {"User-Agent": "Mozilla/5.0 (BCE-Ingestion/1.0)", "Accept-Language": "fr,nl"}
    all_pubs: list[dict] = []
    seen: set[str] = set()

    for page in range(1, max_pages + 1):
        url = ejustice_list_url(bce, language=language, page=page)
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                break
            pubs = parse_ejustice_list_html(r.text, bce)
            if not pubs:
                break
            for pub in pubs:
                if pub["id"] not in seen:
                    seen.add(pub["id"])
                    all_pubs.append(pub)
        except Exception:
            break

    all_pubs.sort(key=lambda p: p["date"], reverse=True)
    return all_pubs


def get_or_scrape_ejustice(bce: str, ejustice_col, cfg: dict) -> list[dict]:
    bce_fmt = _normalize_bce(bce)
    cached = ejustice_col.find_one({"enterprise_number": bce_fmt}, {"_id": 0})
    if cached and cached.get("publications"):
        return cached["publications"]

    pubs = fetch_ejustice_publications(bce_fmt, cfg)
    ejustice_col.update_one(
        {"enterprise_number": bce_fmt},
        {
            "$set": {
                "enterprise_number": bce_fmt,
                "publications": pubs,
                "liste_url": ejustice_list_url(bce_fmt),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return pubs
