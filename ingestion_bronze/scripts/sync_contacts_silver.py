#!/usr/bin/env python3
"""Synchronise les contacts KBO vers enterprise_silver + purge cache statuts demo."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.runtime import require_mongo_db


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    cfg = load_config()
    db = require_mongo_db(cfg, on_warn=log)
    silver = db[cfg["mongodb"]["silver_collection"]]
    contact_path = Path(cfg["kbo"]["source_dir"]) / "contact.csv"

    bce_list = [d["EnterpriseNumber"] for d in silver.find({}, {"EnterpriseNumber": 1})]
    bce_set = set(bce_list)
    log(f"Silver: {len(bce_set):,} entreprises")

    contacts_map: dict[str, list[dict]] = {b: [] for b in bce_set}
    if contact_path.exists():
        for chunk in pd.read_csv(contact_path, dtype=str, chunksize=400_000):
            hits = chunk[chunk["EntityNumber"].isin(bce_set)]
            for _, row in hits.iterrows():
                bce = str(row["EntityNumber"])
                contacts_map.setdefault(bce, []).append(
                    {
                        "EntityNumber": bce,
                        "EntityContact": row.get("EntityContact"),
                        "ContactType": row.get("ContactType"),
                        "Value": row.get("Value"),
                    }
                )
        log("Contacts KBO charges depuis contact.csv")
    else:
        log(f"contact.csv introuvable: {contact_path}")

    updated = 0
    with_contacts = 0
    for bce, contacts in contacts_map.items():
        if not contacts:
            continue
        silver.update_one({"EnterpriseNumber": bce}, {"$set": {"contacts": contacts}})
        updated += 1
        with_contacts += len(contacts)

    statuts = db[cfg["mongodb"]["statuts_collection"]]
    purge = statuts.delete_many({"documents.id": "demo-1"})
    log(f"Contacts injectes: {updated:,} entreprises ({with_contacts:,} lignes)")
    log(f"Cache statuts demo supprime: {purge.deleted_count:,} documents")
    log("Termine.")


if __name__ == "__main__":
    main()
