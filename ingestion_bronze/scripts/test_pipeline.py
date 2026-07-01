#!/usr/bin/env python3
"""Tests locaux du pipeline ingestion bronze (sans Airflow runtime)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyarrow.parquet as pq

from src.config import load_config
from src.db.mongodb import ArtifactStatus, IngestionState, MongoClientFactory, StateDB
from src.db.file_state import FileStateDB
from src.runtime import get_stores


def test_config() -> None:
    cfg = load_config()
    source = Path(cfg["kbo"]["source_dir"])
    assert source.exists(), f"KBO source manquant: {source}"
    assert (source / "enterprise.csv").exists()
    print("[OK] config + source KBO")


def test_state_db_delta() -> None:
    cfg = load_config()
    state_db, _, backend = get_stores(cfg)
    probe = IngestionState(
        source="kbo",
        bce_number=None,
        artifact_type="full_snapshot",
        artifact_id="enterprise",
        snapshot_id="404",
    )
    bronze_enterprise = Path(cfg["bronze"]["base_path"]) / "kbo" / "enterprise" / "snapshot=404"
    assert state_db.is_done(probe) or bronze_enterprise.exists(), (
        "enterprise devrait etre done en State DB ou present en bronze"
    )
    print(f"[OK] delta detection ({backend})")


def test_bronze_parquet_readable() -> None:
    cfg = load_config()
    bronze = Path(cfg["bronze"]["base_path"])
    files = list(bronze.rglob("*.parquet"))
    assert files, "aucun fichier parquet bronze"
    sample = files[0]
    table = pq.read_table(sample)
    assert table.num_rows > 0
    print(f"[OK] parquet lisible ({len(files)} fichiers, ex: {sample.name} {table.num_rows} rows)")


def test_mongodb_if_available() -> None:
    cfg = load_config()
    try:
        factory = MongoClientFactory(cfg["mongodb"]["uri"], cfg["mongodb"]["database"])
        factory.client.admin.command("ping")
        db = factory.db
        StateDB(db[cfg["mongodb"]["state_collection"]])
        print("[OK] MongoDB ping")
    except Exception as e:
        print(f"[SKIP] MongoDB: {e}")


def test_dag_syntax() -> None:
    import importlib.util

    dag_path = ROOT / "dags" / "bce_ingestion_bronze_kbo_dag.py"
    spec = importlib.util.spec_from_file_location("bce_dag", dag_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.dag.dag_id == "bce_ingestion_bronze_kbo"
    print("[OK] DAG import")


def main() -> int:
    tests = [
        test_config,
        test_state_db_delta,
        test_bronze_parquet_readable,
        test_mongodb_if_available,
        test_dag_syntax,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
    print(f"\nResultat: {len(tests) - failed}/{len(tests)} OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
