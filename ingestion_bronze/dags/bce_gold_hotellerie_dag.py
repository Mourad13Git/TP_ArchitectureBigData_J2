"""DAG recalcul Gold annuel (incremental via StateDB)."""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {"owner": "bce", "retries": 1, "retry_delay": timedelta(minutes=5)}


def task_recalc_gold(**context):
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from scripts.run_gold_pipeline import main

    main()


with DAG(
    dag_id="bce_gold_hotellerie",
    default_args=default_args,
    description="Recalcul Gold hotel_gold (entreprises NBB done)",
    schedule="@yearly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["gold", "hotellerie"],
) as dag:
    PythonOperator(
        task_id="recalc_gold",
        python_callable=task_recalc_gold,
    )
