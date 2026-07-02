"""Scraper statuts notaire + SSE."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator

import requests


def normalize_bce(bce: str) -> str:
    raw = bce.replace(".", "").replace(" ", "")
    if len(raw) == 10:
        return f"{raw[:4]}.{raw[4:7]}.{raw[7:]}"
    return bce


async def fetch_statuts_documents(bce: str, cfg: dict) -> list[dict]:
    bce_fmt = bce if "." in bce else f"{bce[:4]}.{bce[4:7]}.{bce[7:]}"
    url = cfg["statuts"]["base_url"].format(bce=bce_fmt.replace(".", ""))
    proxies_list = cfg["statuts"].get("tor_proxies") or [None]

    for proxy in proxies_list:
        try:
            kwargs = {"timeout": 30, "headers": {"User-Agent": "BCE-Ingestion/1.0", "Accept": "application/json"}}
            if proxy:
                kwargs["proxies"] = {"http": proxy, "https": proxy}
            r = requests.get(url, **kwargs)
            if r.status_code != 200:
                continue
            data = r.json()
            if isinstance(data, list):
                return [_normalize_statut(item, i) for i, item in enumerate(data)]
            if isinstance(data, dict):
                items = data.get("statutes") or data.get("content") or data.get("documents") or []
                return [_normalize_statut(item, i) for i, item in enumerate(items)]
        except Exception:
            continue
    return []


def _normalize_statut(item: dict, index: int) -> dict:
    return {
        "id": str(item.get("id") or item.get("reference") or index),
        "titre": item.get("title") or item.get("type") or f"Acte {index + 1}",
        "date": item.get("date") or item.get("depositDate") or "",
        "resume": item.get("summary") or item.get("description") or "",
    }


async def stream_statuts_sse(
    bce: str,
    cfg: dict,
    statuts_col,
) -> AsyncIterator[dict]:
    bce_fmt = normalize_bce(bce)
    cached = statuts_col.find_one({"enterprise_number": bce_fmt}, {"_id": 0})
    if cached and cached.get("documents"):
        for doc in cached["documents"]:
            yield {"event": "statut", "data": json.dumps(doc, ensure_ascii=False)}
        yield {"event": "done", "data": json.dumps({"count": len(cached["documents"]), "source": "cache"})}
        return

    yield {"event": "status", "data": json.dumps({"message": "Scraping statuts.notaire.be..."})}
    documents = await fetch_statuts_documents(bce_fmt, cfg)

    if not documents:
        documents = [
            {"id": "demo-1", "titre": "Statuts coordonnes (demo)", "date": "2021-01-15", "resume": "Demo locale"},
        ]
        yield {"event": "warning", "data": json.dumps({"message": "API notaire indisponible — demo"})}

    for doc in documents:
        await asyncio.sleep(0.3)
        yield {"event": "statut", "data": json.dumps(doc, ensure_ascii=False)}

    statuts_col.update_one(
        {"enterprise_number": bce_fmt},
        {
            "$set": {
                "enterprise_number": bce_fmt,
                "documents": documents,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    yield {"event": "done", "data": json.dumps({"count": len(documents), "source": "scrape"})}
