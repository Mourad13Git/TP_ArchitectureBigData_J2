#!/usr/bin/env python3
"""Pipeline Gold hotel_gold depuis CSV PCMN bronze."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.gold_transform import HotelGoldRepository, run_gold_pipeline
from src.runtime import get_silver_repos, require_mongo_db


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Gold hotel_gold")
    parser.add_argument("--demo", type=int, default=0)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    db = require_mongo_db(cfg, on_warn=log)
    _, _, state_db = get_silver_repos(cfg, db)
    gold_repo = HotelGoldRepository(db[cfg["mongodb"]["gold_collection"]])

    log("\n=== Gold Layer : PCMN -> hotel_gold ===")
    run_gold_pipeline(
        state_db=state_db,
        gold_repo=gold_repo,
        bronze_dir=Path(cfg["bronze"]["base_path"]),
        nbb_subdir=cfg["gold"]["nbb_bronze_subdir"],
        samples_dir=ROOT / cfg["gold"].get("samples_nbb_dir", "samples/nbb_csvs"),
        demo_limit=args.demo,
        on_progress=log,
    )
    log(f"\nTotal hotel_gold: {gold_repo.count():,}")
    log("Termine.")


if __name__ == "__main__":
    main()
