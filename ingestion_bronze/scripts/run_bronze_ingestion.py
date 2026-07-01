#!/usr/bin/env python3
"""
Pipeline ingestion bronze — exécution locale (sans Airflow).

Usage:
  python scripts/run_bronze_ingestion.py --step all
  python scripts/run_bronze_ingestion.py --step kbo --demo 5000
  python scripts/run_bronze_ingestion.py --step seed --demo 5000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.runtime import get_stores
from src.kbo_ingestion import ingest_kbo_table_to_bronze, read_kbo_meta, seed_enterprises_mongodb


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion Bronze KBO")
    parser.add_argument("--step", choices=["all", "kbo", "seed", "status"], default="all")
    parser.add_argument("--demo", type=int, default=0, help="Limiter N entreprises (0=toutes)")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--tables", nargs="*", default=None, help="Tables KBO (ex: enterprise code)")
    parser.add_argument("--quick", action="store_true", help="enterprise + code uniquement")
    args = parser.parse_args()

    cfg = load_config(args.config)
    demo = args.demo or cfg["ingestion"].get("demo_limit_enterprises", 0)

    state_db, enterprise_repo, backend = get_stores(cfg, on_warn=log)
    log(f"Backend catalogue/state : {backend}")

    source_dir = Path(cfg["kbo"]["source_dir"])
    bronze_dir = Path(cfg["bronze"]["base_path"])
    hdfs_prefix = cfg["bronze"]["hdfs_prefix"]
    meta = read_kbo_meta(source_dir)
    snapshot_id = meta.get("ExtractNumber", "unknown")
    tables = args.tables or (["enterprise", "code"] if args.quick else cfg["kbo"]["tables"])

    log(f"Snapshot KBO #{snapshot_id} - source: {source_dir}")

    if args.step in ("all", "kbo"):
        log("\n=== Etape 1 : Ingestion KBO -> Bronze (Parquet) ===")
        for table in tables:
            ingest_kbo_table_to_bronze(
                table=table,
                source_dir=source_dir,
                bronze_dir=bronze_dir,
                hdfs_prefix=hdfs_prefix,
                snapshot_id=snapshot_id,
                state_db=state_db,
                chunk_size=cfg["kbo"]["chunk_size"],
                on_progress=log,
            )

    if args.step in ("all", "seed"):
        log("\n=== Etape 2 : Peuplement MongoDB (catalogue entreprises) ===")
        seed_enterprises_mongodb(
            source_dir=source_dir,
            enterprise_repo=enterprise_repo,
            batch_size=cfg["ingestion"]["batch_size_mongo"],
            demo_limit=demo,
            on_progress=log,
        )

    if args.step in ("all", "status"):
        log("\n=== Etat State DB ===")
        if backend == "mongodb":
            done = state_db.col.count_documents({"status": "done"})
            pending = state_db.col.count_documents({"status": "pending"})
            errors = state_db.col.count_documents({"status": "error"})
        else:
            done = len([v for v in state_db._cache.values() if v.get("status") == "done"])
            pending = len(state_db.list_pending("kbo", 99999))
            errors = len([v for v in state_db._cache.values() if v.get("status") == "error"])
        log(f"  State DB - done: {done}, pending: {pending}, error: {errors}")
        log(f"  Catalogue enterprises: {enterprise_repo.count():,}")

    log("\nTermine.")


if __name__ == "__main__":
    main()
