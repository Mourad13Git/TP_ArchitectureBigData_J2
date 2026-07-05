"""Scraper statuts notaire + fallback eJustice (Moniteur belge)."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator

import requests

STATUT_KEYWORDS = (
    "STATUT",
    "MODIFICATION",
    "COORDON",
    "KAPITAAL",
    "AANDEL",
    "ACTION",
    "FUSION",
    "SCISSION",
    "DISSOLUTION",
    "SIEG",
    "SIEGE",
    "ZETEL",
    "OMZETTING",
    "CONVERSION",
    "VEREFFEN",
    "LIQUID",
)


def normalize_bce(bce: str) -> str:
    raw = bce.replace(".", "").replace(" ", "")
    if len(raw) == 10:
        return f"{raw[:4]}.{raw[4:7]}.{raw[7:]}"
    return bce


def _is_demo_cache(documents: list[dict]) -> bool:
    return len(documents) == 1 and documents[0].get("id") == "demo-1"


def _normalize_statut(item: dict, index: int) -> dict:
    return {
        "id": str(item.get("id") or item.get("reference") or index),
        "titre": item.get("title") or item.get("titre") or item.get("type") or f"Acte {index + 1}",
        "date": item.get("date") or item.get("depositDate") or "",
        "resume": item.get("summary") or item.get("resume") or item.get("description") or "",
        "pdf_url": item.get("pdf_url"),
        "source": item.get("source") or "notaire",
    }


def statuts_from_ejustice(publications: list[dict]) -> list[dict]:
    """Publications Moniteur belge liees aux statuts / actes societaires."""
    results: list[dict] = []
    seen: set[str] = set()
    for pub in publications:
        titre = (pub.get("titre") or "").upper()
        if not any(kw in titre for kw in STATUT_KEYWORDS):
            continue
        pid = pub.get("id") or pub.get("reference")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        results.append(
            {
                "id": pid,
                "titre": pub.get("titre") or "Publication statutaire",
                "date": pub.get("date") or "",
                "resume": f"Publication au Moniteur belge — réf. {pub.get('reference', '')}",
                "pdf_url": pub.get("pdf_url"),
                "source": "ejustice",
            }
        )
    results.sort(key=lambda d: d.get("date") or "", reverse=True)
    return results


async def fetch_statuts_documents(bce: str, cfg: dict) -> list[dict]:
    bce_fmt = normalize_bce(bce)
    bce_nodot = bce_fmt.replace(".", "")
    url = cfg["statuts"]["base_url"].format(bce=bce_nodot)
    proxies_list = cfg["statuts"].get("tor_proxies") or [None]

    for proxy in proxies_list:
        try:
            kwargs = {
                "timeout": 30,
                "headers": {"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            }
            if proxy:
                kwargs["proxies"] = {"http": proxy, "https": proxy}
            r = requests.get(url, **kwargs)
            if r.status_code != 200:
                continue
            content_type = (r.headers.get("content-type") or "").lower()
            if "json" not in content_type:
                continue
            data = r.json()
            if isinstance(data, list) and data:
                return [_normalize_statut(item, i) for i, item in enumerate(data)]
            if isinstance(data, dict):
                items = data.get("statutes") or data.get("content") or data.get("documents") or []
                if items:
                    return [_normalize_statut(item, i) for i, item in enumerate(items)]
        except Exception:
            continue
    return []


async def stream_statuts_sse(
    bce: str,
    cfg: dict,
    statuts_col,
    ejustice_col=None,
) -> AsyncIterator[dict]:
    from api.app.services.ejustice_scraper import get_or_scrape_ejustice

    bce_fmt = normalize_bce(bce)
    cached = statuts_col.find_one({"enterprise_number": bce_fmt}, {"_id": 0})
    if cached and cached.get("documents") and not _is_demo_cache(cached["documents"]):
        for doc in cached["documents"]:
            yield {"event": "statut", "data": json.dumps(doc, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({"count": len(cached["documents"]), "source": "cache"})}
        return

    yield {"event": "status", "data": json.dumps({"message": "Recherche des statuts (notaire + Moniteur belge)..."})}
    documents = await fetch_statuts_documents(bce_fmt, cfg)
    source = "notaire"

    if not documents and ejustice_col is not None:
        pubs = get_or_scrape_ejustice(bce_fmt, ejustice_col, cfg)
        documents = statuts_from_ejustice(pubs)
        source = "ejustice"

    if not documents:
        yield {
            "event": "warning",
            "data": json.dumps({"message": "Aucun statut trouvé pour cette entreprise."}),
        }
        yield {"event": "done", "data": json.dumps({"count": 0, "source": "none"})}
        return

    for doc in documents:
        await asyncio.sleep(0.15)
        yield {"event": "statut", "data": json.dumps(doc, ensure_ascii=False)}

    statuts_col.update_one(
        {"enterprise_number": bce_fmt},
        {
            "$set": {
                "enterprise_number": bce_fmt,
                "documents": documents,
                "source": source,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    yield {"event": "done", "data": json.dumps({"count": len(documents), "source": source})}
