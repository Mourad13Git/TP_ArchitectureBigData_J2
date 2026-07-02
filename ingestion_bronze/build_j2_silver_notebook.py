"""Genere BCE_TP_J2_silver_hotellerie.ipynb"""
import json
import uuid
from pathlib import Path

TP_ROOT = Path(__file__).resolve().parents[1]
OUT = TP_ROOT / "BCE_TP_J2_silver_hotellerie.ipynb"


def md(text: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": text.splitlines(keepends=True),
        "outputs": [],
        "execution_count": None,
    }


cells = [
    md("""# TP Jour 2 — Silver Layer + Scraping Hotellerie

**Objectif :** nettoyer les donnees KBO en couche Silver, cibler le secteur hotelier, scraper les depots NBB depuis 2021.

| Composant | Role |
|---|---|
| `enterprise_finale` | Bronze enrichi (jointures KBO, intact) |
| `enterprise_silver` | Dates normalisees, activites dedupliquees, labels FR |
| `ingestion_state` | Suivi scraping NBB (`pending` / `in_progress` / `done`) |
| Bronze NBB | CSV depots financiers 2021+ |

Code projet : `ingestion_bronze/`
"""),
    md("## 1) Configuration"),
    code("""import sys
from pathlib import Path

ROOT = Path("ingestion_bronze").resolve()
sys.path.insert(0, str(ROOT))

from src.config import load_config

cfg = load_config(ROOT / "config" / "config.yaml")
DEMO = 5000  # mettre 0 pour ingestion complete

print("KBO source :", cfg["kbo"]["source_dir"])
print("Bronze     :", cfg["bronze"]["base_path"])
print("MongoDB    :", cfg["mongodb"]["uri"])
print("Finale     :", cfg["mongodb"]["finale_collection"])
print("Silver     :", cfg["mongodb"]["silver_collection"])
print("Codes NACE hotellerie :", cfg["hotellerie"]["nace_codes"])"""),
    md("""## 2) Connexion MongoDB locale

> Prerequis : `docker run -d -p 27017:27017 --name mongo-bce mongo:7`
"""),
    code("""from src.runtime import get_silver_repos, require_mongo_db

db = require_mongo_db(cfg)
finale_repo, silver_repo, state_db = get_silver_repos(cfg, db)
print("MongoDB OK — base:", cfg["mongodb"]["database"])"""),
    md("""## 3) enterprise_finale — jointures KBO bronze

Assemble `enterprise` + `denomination` + `address` + `activity` + `contact` depuis le bronze Parquet.
"""),
    code("""from src.enterprise_finale import build_enterprise_finale

n_finale = build_enterprise_finale(
    bronze_dir=Path(cfg["bronze"]["base_path"]),
    source_dir=Path(cfg["kbo"]["source_dir"]),
    repo=finale_repo,
    batch_size=cfg["silver"]["batch_size"],
    demo_limit=DEMO,
    on_progress=print,
)
print("Total enterprise_finale :", finale_repo.count())"""),
    md("""## 4) enterprise_silver — nettoyage + labels

| Regle | Transformation |
|---|---|
| Dates | `DD-MM-YYYY` -> `YYYY-MM-DD` |
| Activites | Dedup si meme `NaceCode` + `Classification` |
| Adresses | Garder uniquement `REGO` |
| Denominations | `TypeOfDenomination=1` en premier |
| Labels | `code.csv` -> `StatusLabel`, `JuridicalFormLabel`, `NaceLabel` |
"""),
    code("""from src.code_labels import CodeLabelResolver
from src.kbo_ingestion import read_kbo_meta
from src.silver_transform import build_enterprise_silver, to_silver_document

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
print("Total enterprise_silver :", silver_repo.count())"""),
    md("## 5) Exemple document Silver"),
    code("""sample = silver_repo.col.find_one({}, {"_id": 0})
if sample:
    print("BCE       :", sample.get("EnterpriseNumber"))
    print("StartDate :", sample.get("StartDate"))
    print("Status    :", sample.get("Status"), "->", sample.get("StatusLabel"))
    print("Forme     :", sample.get("JuridicalForm"), "->", sample.get("JuridicalFormLabel"))
    print("Adresses  :", len(sample.get("addresses", [])))
    acts = sample.get("activities", [])[:2]
    for a in acts:
        print(f"  NACE {a.get('NaceCode')} ({a.get('NaceVersion')}) -> {a.get('NaceLabel')}")
else:
    print("Aucun document silver")"""),
    md("""## 6) Filtre hotellerie -> StateDB

9 codes NACE : 55100, 55201, 55202, 55203, 55204, 55209, 55300, 55400, 55900

Filtres : Status=AC, TypeOfEnterprise=2, Classification=MAIN, formes juridiques publiques exclues.
"""),
    code("""from src.hotellerie import seed_hotellerie_state

n_hot = seed_hotellerie_state(
    finale_repo=finale_repo,
    state_db=state_db,
    nace_codes=cfg["hotellerie"]["nace_codes"],
    excluded_forms=cfg["hotellerie"]["excluded_juridical_forms"],
    demo_limit=0,
    on_progress=print,
)
pending = state_db.col.count_documents({"source": "nbb", "status": "pending"})
print("Pending NBB hotellerie :", pending)"""),
    md("""## 7) Scraping NBB CBSO (depots >= 2021)

> L'API `consult.cbso.nbb.be` peut retourner **403** hors cluster Jupyter. La StateDB permet de reprendre sans tout relancer.
"""),
    code("""from src.nbb_ingestion import scrape_hotellerie_pending

NBB_LIMIT = 5  # augmenter sur le cluster

stats = scrape_hotellerie_pending(
    state_db=state_db,
    bronze_dir=Path(cfg["bronze"]["base_path"]),
    hdfs_prefix=cfg["bronze"]["hdfs_prefix"],
    cfg=cfg,
    limit=NBB_LIMIT,
    on_progress=print,
)
print("Stats NBB :", stats)
if stats.get("forbidden"):
    print("-> API 403 : executer cette cellule depuis le cluster Jupyter pour telecharger les CSV")"""),
    md("## 8) Etat final"),
    code("""done = state_db.col.count_documents({"source": "nbb", "status": "done"})
errors = state_db.col.count_documents({"source": "nbb", "status": "error"})
in_progress = state_db.col.count_documents({"source": "nbb", "status": "in_progress"})

print("enterprise_finale :", finale_repo.count())
print("enterprise_silver :", silver_repo.count())
print(f"StateDB nbb — pending={pending}, in_progress={in_progress}, done={done}, error={errors}")

csv_files = list(Path(cfg["bronze"]["base_path"]).rglob("nbb/csvs/**/*.csv"))
print("CSV NBB bronze :", len(csv_files))
for p in csv_files[:3]:
    print(" ", p.relative_to(Path(cfg["bronze"]["base_path"])))"""),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "cells": cells,
}

OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Notebook cree : {OUT}")
