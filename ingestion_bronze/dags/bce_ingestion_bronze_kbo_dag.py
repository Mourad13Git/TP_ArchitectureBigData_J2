"""
DAG Airflow — Ingestion Bronze Jour 2 (KBO + catalogue MongoDB).

Plan 3 jours :
  J1 (ce DAG) : KBO → Bronze HDFS + MongoDB enterprises + State DB
  J2 (à venir) : NBB CSV/PDF depuis MongoDB + delta State DB
  J3 (à venir) : eJustice + Statuts notaire

Branch Git attendue : INGESTION-BRONZE
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# ingestion_bronze/ sur PYTHONPATH (monté dans docker-compose ou AIRFLOW_HOME)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.runtime import get_stores
from src.kbo_ingestion import ingest_kbo_table_to_bronze, read_kbo_meta, seed_enterprises_mongodb

default_args = {
    "owner": "ipssi-bce",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def task_read_meta(**_):
    cfg = load_config()
    meta = read_kbo_meta(Path(cfg["kbo"]["source_dir"]))
    return meta.get("ExtractNumber", "unknown")


def task_ingest_kbo_tables(snapshot_id: str, **_):
    cfg = load_config()
    state_db, _, backend = get_stores(cfg, on_warn=print)
    print(f"Backend State DB: {backend}")
    source_dir = Path(cfg["kbo"]["source_dir"])
    bronze_dir = Path(cfg["bronze"]["base_path"])
    if not source_dir.exists():
        raise FileNotFoundError(f"KBO source introuvable dans le conteneur: {source_dir}")

    for table in cfg["kbo"]["tables"]:
        ingest_kbo_table_to_bronze(
            table=table,
            source_dir=source_dir,
            bronze_dir=bronze_dir,
            hdfs_prefix=cfg["bronze"]["hdfs_prefix"],
            snapshot_id=snapshot_id,
            state_db=state_db,
            chunk_size=cfg["kbo"]["chunk_size"],
            on_progress=print,
        )


def task_seed_mongodb(**_):
    cfg = load_config()
    _, enterprise_repo, backend = get_stores(cfg, on_warn=print)
    print(f"Backend catalogue: {backend}")
    seed_enterprises_mongodb(
        source_dir=Path(cfg["kbo"]["source_dir"]),
        enterprise_repo=enterprise_repo,
        batch_size=cfg["ingestion"]["batch_size_mongo"],
        demo_limit=cfg["ingestion"].get("demo_limit_enterprises", 0),
        on_progress=print,
    )


def task_nbb_delta_placeholder(**_):
    """Jour 2-3 : lire entreprises MongoDB, verifier State DB, telecharger NBB."""
    cfg = load_config()
    state_db, _, _ = get_stores(cfg, on_warn=print)
    pending = state_db.list_pending("nbb", limit=10)
    print(f"NBB pending (placeholder): {len(pending)}")


with DAG(
    dag_id="bce_ingestion_bronze_kbo",
    default_args=default_args,
    description="Ingestion KBO → Bronze + MongoDB + State DB",
    schedule_interval=None,
    start_date=datetime(2026, 6, 29),
    catchup=False,
    tags=["bce", "bronze", "kbo", "INGESTION-BRONZE"],
) as dag:

    read_meta = PythonOperator(
        task_id="read_kbo_snapshot_meta",
        python_callable=task_read_meta,
    )

    ingest_kbo = PythonOperator(
        task_id="ingest_kbo_tables_to_bronze",
        python_callable=task_ingest_kbo_tables,
        op_kwargs={"snapshot_id": "{{ ti.xcom_pull(task_ids='read_kbo_snapshot_meta') }}"},
    )

    seed_mongo = PythonOperator(
        task_id="seed_mongodb_enterprises",
        python_callable=task_seed_mongodb,
    )

    nbb_placeholder = PythonOperator(
        task_id="nbb_delta_detection_placeholder",
        python_callable=task_nbb_delta_placeholder,
    )

    read_meta >> ingest_kbo >> seed_mongo >> nbb_placeholder
