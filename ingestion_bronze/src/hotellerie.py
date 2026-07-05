"""Filtre hotellerie et chargement StateDB."""
from __future__ import annotations

from typing import Callable

from src.code_labels import CodeLabelResolver
from src.db.mongodb import ArtifactStatus, EnterpriseDocumentRepository, IngestionState, StateDB
from src.silver_transform import to_silver_document

HOTEL_NAME_PATTERN = r"hotel|h[oô]tel|motel|auberge|resort|dune|accor|banneux|hospitality"


def hotellerie_mongo_query(nace_codes: list[str], excluded_forms: list[str]) -> dict:
    """Entreprises actives avec NACE hôtellerie OU dénomination évidente."""
    base = {
        "Status": "AC",
        "TypeOfEnterprise": "2",
        "JuridicalForm": {"$nin": excluded_forms},
    }
    return {
        **base,
        "$or": [
            {
                "activities": {
                    "$elemMatch": {
                        "Classification": "MAIN",
                        "NaceCode": {"$in": nace_codes},
                    }
                }
            },
            {"denominations.Denomination": {"$regex": HOTEL_NAME_PATTERN, "$options": "i"}},
        ],
    }


def seed_hotellerie_state(
    finale_repo: EnterpriseDocumentRepository,
    state_db: StateDB,
    nace_codes: list[str],
    excluded_forms: list[str],
    demo_limit: int = 0,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    query = hotellerie_mongo_query(nace_codes, excluded_forms)
    cursor = finale_repo.col.find(query, {"EnterpriseNumber": 1, "_id": 0})
    if demo_limit:
        cursor = cursor.limit(demo_limit)

    total = 0
    for doc in cursor:
        bce = str(doc["EnterpriseNumber"]).replace(".", "")
        state = IngestionState(
            source="nbb",
            bce_number=bce,
            artifact_type="enterprise",
            artifact_id="hotellerie",
            status=ArtifactStatus.PENDING,
        )
        if state_db.is_done(state):
            continue
        existing = state_db.get(state)
        if existing and existing.get("status") == ArtifactStatus.IN_PROGRESS.value:
            continue
        if existing and existing.get("status") == ArtifactStatus.ERROR.value:
            state.error_message = None
        state_db.upsert(state)
        total += 1
        if on_progress and total % 500 == 0:
            on_progress(f"  hotellerie pending: {total:,}...")

    if on_progress:
        on_progress(f"  OK hotellerie StateDB: {total:,} entreprises en pending")
    return total


def sync_hotellerie_to_silver(
    finale_repo: EnterpriseDocumentRepository,
    silver_repo: EnterpriseDocumentRepository,
    labels: CodeLabelResolver,
    nace_codes: list[str],
    excluded_forms: list[str],
    extra_bce: list[str] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    """Upsert toutes les entreprises hotellerie (finale) dans enterprise_silver."""
    query = hotellerie_mongo_query(nace_codes, excluded_forms)
    if extra_bce:
        formatted = []
        for b in extra_bce:
            raw = b.replace(".", "").replace(" ", "")
            if len(raw) == 10:
                formatted.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}")
            else:
                formatted.append(b)
        query = {"$or": [query, {"EnterpriseNumber": {"$in": formatted}}]}

    cursor = finale_repo.col.find(query, {"_id": 0})
    total = 0
    batch: list[dict] = []
    for doc in cursor:
        batch.append(to_silver_document(doc, labels))
        if len(batch) >= 500:
            silver_repo.bulk_upsert(batch)
            total += len(batch)
            batch = []
            if on_progress:
                on_progress(f"  sync silver hotellerie: {total:,}...")
    if batch:
        silver_repo.bulk_upsert(batch)
        total += len(batch)
    if on_progress:
        on_progress(f"  OK sync silver hotellerie: {total:,} documents")
    return total
