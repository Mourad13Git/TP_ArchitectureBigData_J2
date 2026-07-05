#!/usr/bin/env python3
"""Ajoute l'exercice 2025 et recalcule hotel_gold."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.gold_transform import HotelGoldRepository, run_gold_pipeline
from src.nbb_ingestion import extend_fiscal_years
from src.runtime import get_silver_repos, require_mongo_db

PRIORITY_SAMPLES = [
    "0339226816",
    "0413483185",
    "0451368516",
    "0800083516",
    "0417106235",
    "0440515206",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    cfg = load_config()
    db = require_mongo_db(cfg, on_warn=log)
    _, _, state_db = get_silver_repos(cfg, db)
    gold_repo = HotelGoldRepository(db[cfg["mongodb"]["gold_collection"]])
    bronze_dir = Path(cfg["bronze"]["base_path"])
    samples_dir = ROOT / cfg["gold"]["samples_nbb_dir"]

    log("\n=== Extension exercice 2025 (NBB CSV) ===")
    extend_fiscal_years(
        bronze_dir=bronze_dir,
        hdfs_prefix=cfg["bronze"]["hdfs_prefix"],
        state_db=state_db,
        years=(2025,),
        base_year=2024,
        samples_root=samples_dir,
        on_progress=log,
    )

    log("\n=== Recalcul Gold ===")
    run_gold_pipeline(
        state_db=state_db,
        gold_repo=gold_repo,
        bronze_dir=bronze_dir,
        nbb_subdir=cfg["gold"]["nbb_bronze_subdir"],
        samples_dir=samples_dir,
        on_progress=log,
    )

    sample = gold_repo.get("0413.483.185")
    years = [y.get("year") for y in (sample or {}).get("years", [])]
    log(f"\nAccor annees gold: {years}")
    log(f"Total hotel_gold: {gold_repo.count():,}")
    log("Termine.")


if __name__ == "__main__":
    main()
