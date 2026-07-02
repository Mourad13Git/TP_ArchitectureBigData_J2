"""Filtre hotellerie et chargement StateDB."""
from __future__ import annotations

from typing import Callable

from src.db.mongodb import ArtifactStatus, EnterpriseDocumentRepository, IngestionState, StateDB


def seed_hotellerie_state(
    finale_repo: EnterpriseDocumentRepository,
    state_db: StateDB,
    nace_codes: list[str],
    excluded_forms: list[str],
    demo_limit: int = 0,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    query = {
        "Status": "AC",
        "TypeOfEnterprise": "2",
        "JuridicalForm": {"$nin": excluded_forms},
        "activities": {
            "$elemMatch": {
                "Classification": "MAIN",
                "NaceCode": {"$in": nace_codes},
            }
        },
    }
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
