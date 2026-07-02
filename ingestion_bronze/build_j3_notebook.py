"""Genere BCE_TP_J3_gold_api.ipynb"""
import json
import uuid
from pathlib import Path

TP_ROOT = Path(__file__).resolve().parents[1]
OUT = TP_ROOT / "BCE_TP_J3_gold_api.ipynb"


def md(t):
    return {"cell_type": "markdown", "id": uuid.uuid4().hex[:8], "metadata": {}, "source": t.splitlines(keepends=True)}


def code(t):
    return {"cell_type": "code", "id": uuid.uuid4().hex[:8], "metadata": {}, "source": t.splitlines(keepends=True), "outputs": [], "execution_count": None}


cells = [
    md("# TP Jour 3 — Gold Layer + API FastAPI + Frontend React\n\nObjectif : ratios PCMN -> `hotel_gold`, API REST, Sankey React."),
    md("## 1) Pipeline Gold"),
    code("""import sys
from pathlib import Path
ROOT = Path("ingestion_bronze").resolve()
sys.path.insert(0, str(ROOT))
# !python ingestion_bronze/scripts/seed_j3_demo.py
# !python ingestion_bronze/scripts/run_gold_pipeline.py --demo 10"""),
    md("## 2) API FastAPI"),
    code("""# Terminal : cd TP1 && python api/run_api.py
# http://localhost:8000/health
# http://localhost:8000/search?q=hotel"""),
    md("## 3) Frontend React"),
    code("""# Terminal : cd frontend && npm install && npm run dev
# http://localhost:5173"""),
    md("## 4) DAG Airflow Gold annuel"),
    code("""from pathlib import Path
print((Path("ingestion_bronze/dags/bce_gold_hotellerie_dag.py")).read_text(encoding="utf-8")[:800])"""),
]

nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "cells": cells}
OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Notebook cree : {OUT}")
