"""Construction de enterprise_finale depuis le bronze KBO."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from src.bronze_reader import group_by_entity, read_enterprise_batch, read_related_rows
from src.db.mongodb import EnterpriseDocumentRepository
from src.kbo_ingestion import read_kbo_meta


RELATED_TABLES = ("denomination", "address", "activity", "contact")


def build_enterprise_document(
    row: dict,
    denominations: list[dict],
    addresses: list[dict],
    activities: list[dict],
    contacts: list[dict],
) -> dict:
    doc = {k: (None if pd.isna(v) else v) for k, v in row.items()}
    doc["denominations"] = denominations
    doc["addresses"] = addresses
    doc["activities"] = activities
    doc["contacts"] = contacts
    return doc


def build_enterprise_finale(
    bronze_dir: Path,
    source_dir: Path,
    repo: EnterpriseDocumentRepository,
    batch_size: int = 5_000,
    demo_limit: int = 0,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    meta = read_kbo_meta(source_dir)
    snapshot_id = meta.get("ExtractNumber", "unknown")
    total = 0
    offset = 0

    while True:
        if demo_limit and total >= demo_limit:
            break
        batch_limit = batch_size if not demo_limit else min(batch_size, demo_limit - total)
        enterprises = read_enterprise_batch(bronze_dir, snapshot_id, offset, batch_limit)
        if enterprises.empty:
            break

        bce_numbers = enterprises["EnterpriseNumber"].astype(str).tolist()
        related = {
            table: group_by_entity(
                read_related_rows(bronze_dir, table, snapshot_id, bce_numbers),
                "EntityNumber",
            )
            for table in RELATED_TABLES
        }

        documents = []
        for _, row in enterprises.iterrows():
            bce = str(row["EnterpriseNumber"])
            documents.append(
                build_enterprise_document(
                    row.to_dict(),
                    related["denomination"].get(bce, []),
                    related["address"].get(bce, []),
                    related["activity"].get(bce, []),
                    related["contact"].get(bce, []),
                )
            )

        repo.bulk_upsert(documents)
        total += len(documents)
        offset += len(enterprises)

        if on_progress:
            on_progress(f"  enterprise_finale: {total:,} documents...")
        if len(enterprises) < batch_limit:
            break

    if on_progress:
        on_progress(f"  OK enterprise_finale: {total:,} documents")
    return total
