#!/usr/bin/env python3
"""
Pipeline Silver + Hotellerie + Scraping NBB (local MongoDB).

Usage:
  python scripts/run_silver_pipeline.py --step all --demo 5000
  python scripts/run_silver_pipeline.py --step finale --demo 1000
  python scripts/run_silver_pipeline.py --step silver
  python scripts/run_silver_pipeline.py --step hotellerie
  python scripts/run_silver_pipeline.py --step nbb --limit 20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.code_labels import CodeLabelResolver
from src.config import load_config
from src.enterprise_finale import build_enterprise_finale
from src.hotellerie import seed_hotellerie_state
from src.kbo_ingestion import read_kbo_meta
from src.nbb_ingestion import scrape_hotellerie_pending
from src.runtime import get_silver_repos, require_mongo_db
from src.silver_transform import build_enterprise_silver


def log(msg: str) -> None:
  print(msg, flush=True)


def main() -> None:
  parser = argparse.ArgumentParser(description="Pipeline Silver + Hotellerie + NBB")
  parser.add_argument(
    "--step",
    choices=["all", "finale", "silver", "hotellerie", "nbb", "status"],
    default="all",
  )
  parser.add_argument("--demo", type=int, default=0, help="Limiter N entreprises")
  parser.add_argument("--limit", type=int, default=50, help="Limite scraping NBB")
  parser.add_argument("--config", type=Path, default=None)
  args = parser.parse_args()

  cfg = load_config(args.config)
  demo = args.demo
  db = require_mongo_db(cfg, on_warn=log)
  finale_repo, silver_repo, state_db = get_silver_repos(cfg, db)

  bronze_dir = Path(cfg["bronze"]["base_path"])
  source_dir = Path(cfg["kbo"]["source_dir"])
  batch_size = int(cfg.get("silver", {}).get("batch_size", 5_000))
  meta = read_kbo_meta(source_dir)
  snapshot_id = meta.get("ExtractNumber", "unknown")

  if args.step in ("all", "finale"):
    log("\n=== Etape 1 : enterprise_finale (bronze KBO -> MongoDB) ===")
    build_enterprise_finale(
      bronze_dir=bronze_dir,
      source_dir=source_dir,
      repo=finale_repo,
      batch_size=batch_size,
      demo_limit=demo,
      on_progress=log,
    )

  if args.step in ("all", "silver"):
    log("\n=== Etape 2 : enterprise_silver (nettoyage + labels) ===")
    labels = CodeLabelResolver.from_parquet(bronze_dir, snapshot_id)
    build_enterprise_silver(
      finale_repo=finale_repo,
      silver_repo=silver_repo,
      labels=labels,
      batch_size=batch_size,
      demo_limit=demo,
      on_progress=log,
    )

  if args.step in ("all", "hotellerie"):
    log("\n=== Etape 3 : filtre hotellerie -> StateDB pending ===")
    seed_hotellerie_state(
      finale_repo=finale_repo,
      state_db=state_db,
      nace_codes=cfg["hotellerie"]["nace_codes"],
      excluded_forms=cfg["hotellerie"]["excluded_juridical_forms"],
      demo_limit=demo,
      on_progress=log,
    )

  if args.step in ("all", "nbb"):
    log("\n=== Etape 4 : scraping NBB CBSO (2021+) ===")
    stats = scrape_hotellerie_pending(
      state_db=state_db,
      bronze_dir=bronze_dir,
      hdfs_prefix=cfg["bronze"]["hdfs_prefix"],
      cfg=cfg,
      limit=args.limit,
      samples_root=ROOT / cfg["gold"].get("samples_nbb_dir", "samples/nbb_csvs"),
      allow_sample_fallback=True,
      on_progress=log,
    )
    log(
        f"  NBB resultat: processed={stats['processed']}, done={stats['done']}, "
        f"errors={stats['errors']}, filings={stats['filings']}, "
        f"rate_limited={stats['rate_limited']}, forbidden={stats.get('forbidden', False)}, "
        f"sample_fallback={stats.get('sample_fallback', 0)}"
    )

  if args.step in ("all", "status"):
    log("\n=== Etat collections ===")
    log(f"  enterprise_finale: {finale_repo.count():,}")
    log(f"  enterprise_silver: {silver_repo.count():,}")
    pending = state_db.col.count_documents({"source": "nbb", "status": "pending"})
    done = state_db.col.count_documents({"source": "nbb", "status": "done"})
    in_progress = state_db.col.count_documents({"source": "nbb", "status": "in_progress"})
    log(f"  StateDB nbb: pending={pending}, in_progress={in_progress}, done={done}")

  log("\nTermine.")


if __name__ == "__main__":
  main()
