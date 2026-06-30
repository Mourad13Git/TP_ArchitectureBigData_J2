#!/usr/bin/env python3
"""Execute les cellules code du notebook J2 (hors Airflow shell)."""
from __future__ import annotations

import sys
from pathlib import Path

TP_ROOT = Path(__file__).resolve().parents[2]
ROOT = TP_ROOT / "ingestion_bronze"
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db.mongodb import IngestionState, ArtifactStatus

print("=== Cell 2: config ===")
cfg = load_config(ROOT / "config" / "config.yaml")
print("KBO source :", cfg["kbo"]["source_dir"])
print("Bronze     :", cfg["bronze"]["base_path"])
print("MongoDB    :", cfg["mongodb"]["uri"])

print("\n=== Cell 3: State DB examples ===")
examples = [
    IngestionState("kbo", None, "full_snapshot", "enterprise", snapshot_id="404", status=ArtifactStatus.DONE),
    IngestionState("nbb", "878065378", "pdf", "2024-00001234", year=2024, status=ArtifactStatus.PENDING),
]
for s in examples:
    print(s.state_key, "->", s.status.value)

print("\n=== Cell 4: bronze check ===")
bronze = (ROOT / cfg["bronze"]["base_path"]).resolve()
if bronze.exists():
    for p in sorted(bronze.rglob("*.parquet"))[:5]:
        print(p.relative_to(ROOT), "-", p.stat().st_size // 1024, "KB")
else:
    print("Bronze pas encore cree")

print("\n=== Cell 5: DAG file ===")
dag_path = ROOT / "dags" / "bce_ingestion_bronze_kbo_dag.py"
text = dag_path.read_text(encoding="utf-8")[:400].replace("\u2192", "->")
print(text, "...")
print("\nNotebook J2 cells OK")
