"""Scraper kbopub — dirigeants."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


class KBOParser:
    ROLE_KEYS = [
        "Bestuurder", "Gedelegeerd bestuurder", "Administrateur", "Directeur",
        "Gérant", "Commissaire", "Voorzitter", "Persoon belast met dagelijks bestuur",
    ]

    def __init__(self, bce_nodot: str, base_url: str):
        url = f"{base_url}?ondernemingsnummer={bce_nodot}"
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "fr,nl"},
            timeout=30,
        )
        r.raise_for_status()
        self.soup = BeautifulSoup(r.text, "lxml")

    def dirigeants(self) -> list[dict]:
        dirs, seen = [], set()
        for table in self.soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                role = cells[0].get_text(" ", strip=True)
                if role not in self.ROLE_KEYS:
                    continue
                nom = re.sub(r"\s+", " ", cells[1].get_text(" ", strip=True)).strip()
                depuis = cells[2].get_text(" ", strip=True) if len(cells) > 2 else ""
                if nom and (role, nom) not in seen:
                    seen.add((role, nom))
                    dirs.append({"role": role, "nom": nom, "depuis": depuis})
        return dirs


def get_or_scrape_officers(bce: str, officers_col, cfg: dict) -> list[dict]:
    bce_nodot = bce.replace(".", "")
    cached = officers_col.find_one({"enterprise_number": bce}, {"_id": 0})
    if cached and cached.get("dirigeants"):
        return cached["dirigeants"]

    try:
        parser = KBOParser(bce_nodot, cfg["kbopub"]["base_url"])
        dirs = parser.dirigeants()
    except Exception:
        dirs = []

    officers_col.update_one(
        {"enterprise_number": bce},
        {
            "$set": {
                "enterprise_number": bce,
                "dirigeants": dirs,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return dirs
