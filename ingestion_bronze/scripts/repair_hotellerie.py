#!/usr/bin/env python3
"""
Repare hotellerie : ingest BCE manquants, sync silver, NBB fallback local, gold.

Usage:
  python scripts/repair_hotellerie.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.code_labels import CodeLabelResolver
from src.config import load_config
from src.gold_transform import HotelGoldRepository, run_gold_pipeline
from src.hotellerie import seed_hotellerie_state, sync_hotellerie_to_silver
from src.kbo_lookup import load_enterprises_from_kbo
from src.kbo_ingestion import read_kbo_meta
from src.nbb_ingestion import reprocess_nbb_errors_with_samples, scrape_hotellerie_pending
from src.runtime import get_silver_repos, require_mongo_db

PRIORITY_BCE = [
    "0413.483.185",  # Accor Hotels Belgium
    "0451.368.516",  # Hotel des Dunes
    "0800.083.516",  # Dunehotel Nieuwpoort
    "0417.106.235",  # Maison Halleux (Banneux)
    "0440.515.206",  # Hospitalite Banneux
    "0339.226.816",  # Hotel Demo Bruxelles
]


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    cfg = load_config()
    db = require_mongo_db(cfg, on_warn=log)
    finale_repo, silver_repo, state_db = get_silver_repos(cfg, db)
    gold_repo = HotelGoldRepository(db[cfg["mongodb"]["gold_collection"]])

    source_dir = Path(cfg["kbo"]["source_dir"])
    bronze_dir = Path(cfg["bronze"]["base_path"])
    samples_dir = ROOT / cfg["gold"]["samples_nbb_dir"]
    meta = read_kbo_meta(source_dir)
    snapshot_id = meta.get("ExtractNumber", "unknown")

    log("\n=== 1. Ingestion KBO ciblee (hotels manquants) ===")
    docs = load_enterprises_from_kbo(source_dir, PRIORITY_BCE)
    if docs:
        finale_repo.bulk_upsert(docs)
        log(f"  {len(docs)} entreprises ajoutees/mises a jour dans enterprise_finale")
    else:
        log("  Aucun document KBO charge (verifier source_dir)")

    log("\n=== 2. Sync hotellerie -> enterprise_silver ===")
    try:
        labels = CodeLabelResolver.from_parquet(bronze_dir, snapshot_id)
    except FileNotFoundError:
        labels = CodeLabelResolver.from_csv(source_dir)
        log("  Labels depuis code.csv (bronze parquet absent)")
    sync_hotellerie_to_silver(
        finale_repo=finale_repo,
        silver_repo=silver_repo,
        labels=labels,
        nace_codes=cfg["hotellerie"]["nace_codes"],
        excluded_forms=cfg["hotellerie"]["excluded_juridical_forms"],
        extra_bce=PRIORITY_BCE,
        on_progress=log,
    )

    log("\n=== 3. StateDB hotellerie + NBB (fallback echantillons) ===")
    seed_hotellerie_state(
        finale_repo=finale_repo,
        state_db=state_db,
        nace_codes=cfg["hotellerie"]["nace_codes"],
        excluded_forms=cfg["hotellerie"]["excluded_juridical_forms"],
        on_progress=log,
    )
    reprocess_nbb_errors_with_samples(
        state_db, bronze_dir, cfg["bronze"]["hdfs_prefix"], samples_dir, on_progress=log
    )
    stats = scrape_hotellerie_pending(
        state_db=state_db,
        bronze_dir=bronze_dir,
        hdfs_prefix=cfg["bronze"]["hdfs_prefix"],
        cfg=cfg,
        limit=500,
        samples_root=samples_dir,
        allow_sample_fallback=True,
        on_progress=log,
    )
    log(f"  NBB: done={stats['done']}, sample_fallback={stats.get('sample_fallback', 0)}, errors={stats['errors']}")

    log("\n=== 4. Pipeline Gold ===")
    run_gold_pipeline(
        state_db=state_db,
        gold_repo=gold_repo,
        bronze_dir=bronze_dir,
        nbb_subdir=cfg["gold"]["nbb_bronze_subdir"],
        samples_dir=samples_dir,
        on_progress=log,
    )

    log("\n=== Etat final ===")
    log(f"  enterprise_silver: {silver_repo.count():,}")
    log(f"  hotel_gold: {gold_repo.count():,}")
    for term in ["accor", "dune", "banneux", "hotel"]:
        n = silver_repo.col.count_documents(
            {
                "$or": [
                    {"denominations.Denomination": {"$regex": term, "$options": "i"}},
                    {"addresses.MunicipalityFR": {"$regex": term, "$options": "i"}},
                ]
            }
        )
        log(f"  recherche '{term}' dans silver: {n}")
    log("\nReparation terminee.")


if __name__ == "__main__":
    main()
