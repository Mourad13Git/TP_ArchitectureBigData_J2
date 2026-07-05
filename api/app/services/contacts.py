"""Normalisation et enrichissement des contacts entreprise (KBO + kbopub)."""
from __future__ import annotations

from datetime import datetime, timezone

from api.app.services.kbopub import KBOParser

CONTACT_TYPE_LABELS = {
    "TEL": "Téléphone",
    "EMAIL": "E-mail",
    "WEB": "Site web",
    "FAX": "Fax",
}

NO_DATA_MARKERS = (
    "geen gegevens",
    "aucune donnée",
    "pas de données",
    "no data",
    "keine angaben",
)


def _normalize_bce(bce: str) -> str:
    raw = bce.replace(".", "").replace(" ", "")
    if len(raw) == 10:
        return f"{raw[:4]}.{raw[4:7]}.{raw[7:]}"
    return bce


def _is_valid_value(value: str) -> bool:
    text = (value or "").strip()
    if not text or text in ("—", "-", "nan", "None"):
        return False
    lower = text.lower()
    return not any(marker in lower for marker in NO_DATA_MARKERS)


def contacts_from_silver(silver_doc: dict) -> list[dict]:
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for row in silver_doc.get("contacts") or []:
        ctype = str(row.get("ContactType", "")).strip().upper()
        value = str(row.get("Value", "")).strip()
        if not ctype or not _is_valid_value(value):
            continue
        key = (ctype, value)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "type": ctype,
                "label": CONTACT_TYPE_LABELS.get(ctype, ctype),
                "value": value,
                "source": "kbo",
            }
        )
    return items


def merge_contacts(kbo_items: list[dict], kbopub_items: list[dict]) -> list[dict]:
    merged = list(kbo_items)
    seen = {(i["type"], i["value"]) for i in merged}
    for item in kbopub_items:
        key = (item["type"], item["value"])
        if key not in seen:
            seen.add(key)
            merged.append(item)
    return merged


def get_enterprise_contacts(bce: str, silver_doc: dict, contacts_col, cfg: dict) -> list[dict]:
    bce_fmt = _normalize_bce(bce)
    cached = contacts_col.find_one({"enterprise_number": bce_fmt}, {"_id": 0})
    if cached and cached.get("items"):
        return cached["items"]

    kbo_items = contacts_from_silver(silver_doc)
    kbopub_items: list[dict] = []
    try:
        parser = KBOParser(bce_fmt.replace(".", ""), cfg["kbopub"]["base_url"])
        kbopub_items = parser.contacts()
    except Exception:
        pass

    items = merge_contacts(kbo_items, kbopub_items)
    contacts_col.update_one(
        {"enterprise_number": bce_fmt},
        {
            "$set": {
                "enterprise_number": bce_fmt,
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return items
