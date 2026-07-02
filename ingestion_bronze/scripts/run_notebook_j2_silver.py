#!/usr/bin/env python3
"""Execute les cellules code du notebook J2 Silver (hors Jupyter)."""
from __future__ import annotations

import sys
from pathlib import Path

TP_ROOT = Path(__file__).resolve().parents[2]
ROOT = TP_ROOT / "ingestion_bronze"
sys.path.insert(0, str(ROOT))

from src.code_labels import CodeLabelResolver
from src.config import load_config
from src.enterprise_finale import build_enterprise_finale
from src.hotellerie import seed_hotellerie_state
from src.kbo_ingestion import read_kbo_meta
from src.nbb_ingestion import scrape_hotellerie_pending
from src.runtime import get_silver_repos, require_mongo_db
from src.silver_transform import build_enterprise_silver

DEMO = 5000
NBB_LIMIT = 5


def main() -> int:
    print("=== Cell 1: config ===")
    cfg = load_config(ROOT / "config" / "config.yaml")
    print("MongoDB:", cfg["mongodb"]["uri"])
    print("DEMO:", DEMO)

    print("\n=== Cell 2: MongoDB ===")
    db = require_mongo_db(cfg)
    finale_repo, silver_repo, state_db = get_silver_repos(cfg, db)
    print("MongoDB OK")

    print("\n=== Cell 3: enterprise_finale ===")
    n_finale = build_enterprise_finale(
        bronze_dir=Path(cfg["bronze"]["base_path"]),
        source_dir=Path(cfg["kbo"]["source_dir"]),
        repo=finale_repo,
        batch_size=cfg["silver"]["batch_size"],
        demo_limit=DEMO,
        on_progress=print,
    )
    print("Total finale:", finale_repo.count(), "| batch:", n_finale)

    print("\n=== Cell 4: enterprise_silver ===")
    meta = read_kbo_meta(Path(cfg["kbo"]["source_dir"]))
    snapshot_id = meta.get("ExtractNumber", "unknown")
    labels = CodeLabelResolver.from_parquet(Path(cfg["bronze"]["base_path"]), snapshot_id)
    n_silver = build_enterprise_silver(
        finale_repo=finale_repo,
        silver_repo=silver_repo,
        labels=labels,
        batch_size=cfg["silver"]["batch_size"],
        demo_limit=DEMO,
        on_progress=print,
    )
    print("Total silver:", silver_repo.count(), "| batch:", n_silver)

    print("\n=== Cell 5: sample silver ===")
    sample = silver_repo.col.find_one({}, {"_id": 0})
    if sample:
        print("BCE:", sample.get("EnterpriseNumber"))
        print("StartDate:", sample.get("StartDate"))
        print("StatusLabel:", sample.get("StatusLabel"))
    else:
        print("Aucun document silver")

    print("\n=== Cell 6: hotellerie ===")
    n_hot = seed_hotellerie_state(
        finale_repo=finale_repo,
        state_db=state_db,
        nace_codes=cfg["hotellerie"]["nace_codes"],
        excluded_forms=cfg["hotellerie"]["excluded_juridical_forms"],
        demo_limit=0,
        on_progress=print,
    )
    pending = state_db.col.count_documents({"source": "nbb", "status": "pending"})
    print("Hotellerie seeded:", n_hot, "| pending:", pending)

    print("\n=== Cell 7: NBB scraping ===")
    stats = scrape_hotellerie_pending(
        state_db=state_db,
        bronze_dir=Path(cfg["bronze"]["base_path"]),
        hdfs_prefix=cfg["bronze"]["hdfs_prefix"],
        cfg=cfg,
        limit=NBB_LIMIT,
        on_progress=print,
    )
    print("Stats NBB:", stats)

    print("\n=== Cell 8: status ===")
    done = state_db.col.count_documents({"source": "nbb", "status": "done"})
    errors = state_db.col.count_documents({"source": "nbb", "status": "error"})
    print("finale:", finale_repo.count(), "| silver:", silver_repo.count())
    print(f"nbb pending={pending}, done={done}, error={errors}")
    csv_files = list(Path(cfg["bronze"]["base_path"]).rglob("nbb/csvs/**/*.csv"))
    print("CSV NBB:", len(csv_files))

    print("\nNotebook J2 Silver cells OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
