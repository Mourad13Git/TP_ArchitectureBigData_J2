"""Génère BCE_TP_J2_ingestion_bronze.ipynb"""
import json, uuid
from pathlib import Path

def md(t): return {"cell_type":"markdown","id":uuid.uuid4().hex[:8],"metadata":{},"source":t.splitlines(keepends=True)}
def code(t): return {"cell_type":"code","id":uuid.uuid4().hex[:8],"metadata":{},"source":t.splitlines(keepends=True),"outputs":[],"execution_count":None}

cells = [
md("""# TP Jour 2 — Architecture globale : Ingestion Bronze

**Objectif du jour :** passer de 3 entreprises à **toutes les entreprises belges** (~2M BCE).

| Composant | Rôle |
|---|---|
| **MongoDB** `enterprises` | Catalogue de tous les numéros BCE |
| **State DB** `ingestion_state` | Meta : delta detection, pas de re-téléchargement |
| **Bronze** (HDFS / local) | Parquet KBO, futurs PDF/CSV NBB |
| **Airflow** | DAG `bce_ingestion_bronze_kbo` |

Code projet : `ingestion_bronze/`
"""),
md("## 1) Vue d'ensemble de l'architecture"),
code("""from IPython.display import Image, display
# Schéma logique
print(\"\"\"
KBO CSV (full)  ──▶  Bronze Parquet     MongoDB enterprises (2M)
       │                    │                    │
       └──────── State DB (ingestion_state) ────┘
                              │
                    Airflow DAG (delta)
                              │
              NBB / eJustice / Statuts (J2-J3)
\"\"\")"""),
md("## 2) Configuration"),
code("""import sys
from pathlib import Path

ROOT = Path("ingestion_bronze").resolve()
sys.path.insert(0, str(ROOT))

from src.config import load_config
cfg = load_config(ROOT / "config" / "config.yaml")
print("KBO source :", cfg["kbo"]["source_dir"])
print("Bronze     :", cfg["bronze"]["base_path"])
print("MongoDB    :", cfg["mongodb"]["uri"])
print("Tables KBO :", cfg["kbo"]["tables"])"""),
md("""## 3) State DB — principe delta detection

Chaque artefact ingéré a une clé unique. Si `status=done`, on **skip**.
"""),
code("""from src.db.mongodb import IngestionState, ArtifactStatus

examples = [
    IngestionState("kbo", None, "full_snapshot", "enterprise", snapshot_id="404", status=ArtifactStatus.DONE),
    IngestionState("nbb", "878065378", "pdf", "2024-00001234", year=2024, status=ArtifactStatus.PENDING),
    IngestionState("nbb", "878065378", "csv_nbb", "2024-00001234", year=2024, status=ArtifactStatus.DONE,
                   hdfs_path="/data/bronze/nbb/csvs/878065378/2024.csv"),
]
for s in examples:
    print(s.state_key, "→", s.status.value, "|", s.hdfs_path or s.local_path or "(pending)")"""),
md("""## 4) Ingestion KBO → Bronze (démo)

> Prérequis MongoDB : `docker run -d -p 27017:27017 mongo:7`

Mode `--demo 5000` pour tester rapidement. Enlever la limite pour l'ingestion complète.
"""),
code("""# Exécution pipeline (démo 5000 entreprises)
# Décommenter pour lancer :

# !cd ingestion_bronze && python scripts/run_bronze_ingestion.py --step all --demo 5000

# Vérification bronze local
bronze = Path(cfg["bronze"]["base_path"])
if bronze.exists():
    for p in sorted(bronze.rglob("*.parquet"))[:5]:
        print(p.relative_to(bronze.parent), "—", p.stat().st_size // 1024, "KB")
else:
    print("Bronze pas encore créé — lancer le script ci-dessus")"""),
md("## 5) DAG Airflow"),
code("""# DAG : ingestion_bronze/dags/bce_ingestion_bronze_kbo_dag.py
# Tâches : read_meta → ingest_kbo → seed_mongo → nbb_placeholder

from pathlib import Path
dag_path = ROOT / "dags" / "bce_ingestion_bronze_kbo_dag.py"
print(dag_path.read_text(encoding="utf-8")[:1200], "...")"""),
md("""## 6) Prochaines étapes (J2-J3)

1. DAG NBB : lire `enterprises` MongoDB → API CBSO → PDF/CSV bronze
2. DAG eJustice + Statuts notaire
3. Couche Silver (jointures, nettoyage) → Gold (insights)

**Branche Git :** `INGESTION-BRONZE`
"""),
]

nb = {"nbformat":4,"nbformat_minor":5,"metadata":{"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"name":"python"}},"cells":cells}
Path(r"d:\IPSSI\architecture big data M2\TP1\BCE_TP_J2_ingestion_bronze.ipynb").write_text(json.dumps(nb,ensure_ascii=False,indent=1),encoding="utf-8")
print("Notebook J2 créé")
