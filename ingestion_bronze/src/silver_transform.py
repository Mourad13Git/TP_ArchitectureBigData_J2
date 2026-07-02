"""Transformations Silver : enterprise_finale -> enterprise_silver."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from src.code_labels import CodeLabelResolver
from src.db.mongodb import EnterpriseDocumentRepository


def normalize_date(value: str | None) -> str | None:
    if not value or str(value).strip() in ("", "nan", "None"):
        return None
    text = str(value).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def dedupe_activities(activities: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result = []
    for activity in activities:
        key = (str(activity.get("NaceCode", "")).strip(), str(activity.get("Classification", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(activity)
    return result


def filter_rego_addresses(addresses: list[dict]) -> list[dict]:
    return [addr for addr in addresses if str(addr.get("TypeOfAddress", "")).strip() == "REGO"]


def sort_denominations(denominations: list[dict]) -> list[dict]:
    def sort_key(item: dict) -> tuple[int, str]:
        primary = 0 if str(item.get("TypeOfDenomination", "")).strip() == "1" else 1
        return primary, str(item.get("Denomination", ""))

    return sorted(denominations, key=sort_key)


def to_silver_document(doc: dict, labels: CodeLabelResolver) -> dict:
    silver = dict(doc)
    silver["StartDate"] = normalize_date(doc.get("StartDate"))
    silver["addresses"] = filter_rego_addresses(doc.get("addresses", []))
    silver["denominations"] = sort_denominations(doc.get("denominations", []))
    silver["activities"] = dedupe_activities(doc.get("activities", []))

    silver["StatusLabel"] = labels.label("Status", doc.get("Status"))
    silver["JuridicalFormLabel"] = labels.label("JuridicalForm", doc.get("JuridicalForm"))
    silver["JuridicalSituationLabel"] = labels.label("JuridicalSituation", doc.get("JuridicalSituation"))
    silver["TypeOfEnterpriseLabel"] = labels.label("TypeOfEnterprise", doc.get("TypeOfEnterprise"))

    enriched_activities = []
    for activity in silver["activities"]:
        item = dict(activity)
        item["NaceLabel"] = labels.nace_label(item.get("NaceVersion", ""), item.get("NaceCode", ""))
        item["ClassificationLabel"] = labels.label("Classification", item.get("Classification"))
        item["ActivityGroupLabel"] = labels.label("ActivityGroup", item.get("ActivityGroup"))
        enriched_activities.append(item)
    silver["activities"] = enriched_activities
    return silver


def build_enterprise_silver(
    finale_repo: EnterpriseDocumentRepository,
    silver_repo: EnterpriseDocumentRepository,
    labels: CodeLabelResolver,
    batch_size: int = 5_000,
    demo_limit: int = 0,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    total = 0
    for batch in finale_repo.iter_documents(batch_size=batch_size, limit=demo_limit or None):
        silver_docs = [to_silver_document(doc, labels) for doc in batch]
        silver_repo.bulk_upsert(silver_docs)
        total += len(silver_docs)
        if on_progress:
            on_progress(f"  enterprise_silver: {total:,} documents...")
    if on_progress:
        on_progress(f"  OK enterprise_silver: {total:,} documents")
    return total
