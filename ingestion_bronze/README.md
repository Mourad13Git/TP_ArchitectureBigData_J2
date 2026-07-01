# Architecture Big Data — Ingestion Bronze (Jour 2)

Pipeline global pour **toutes les entreprises belges** (~2M numéros BCE), avec :

- **MongoDB** : catalogue `enterprises` (tous les numéros BCE)
- **State DB** (collection `ingestion_state`) : meta / delta detection
- **Bronze HDFS** (ou local `data/bronze`) : Parquet KBO, futurs PDF/CSV NBB
- **Airflow** : orchestration des DAGs

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│ KBO Open Data   │────▶│ Bronze (Parquet) │     │ MongoDB             │
│ (CSV full dump) │     │ /data/bronze/kbo │     │ • enterprises (~2M) │
└─────────────────┘     └──────────────────┘     │ • ingestion_state   │
                                                  └──────────┬──────────┘
┌─────────────────┐     ┌──────────────────┐               │
│ NBB / eJustice  │────▶│ Bronze PDF/CSV   │◀──────────────┘
│ (par entreprise)│     │ /data/bronze/nbb │   DAG lit MongoDB +
└─────────────────┘     └──────────────────┘   vérifie State DB
```

### State DB — champs clés

| Champ | Exemple | Rôle |
|---|---|---|
| `source` | `kbo`, `nbb`, `ejustice` | Origine |
| `bce_number` | `0878065378` | Entreprise (null pour snapshot KBO global) |
| `artifact_id` | `activity`, `2024-000123` | Table ou deposit ID |
| `year` | `2024` | Exercice fiscal (NBB) |
| `status` | `pending` / `done` / `error` | Delta detection |
| `hdfs_path` | `/data/bronze/kbo/activity/...` | Chemin cible |
| `snapshot_id` | `404` | Numéro extrait KBO |

Si `status=done` → **pas de re-téléchargement**.

## Jour 1 — Ingestion KBO (aujourd'hui)

### Prérequis

```bash
pip install -r requirements.txt
# MongoDB local
docker run -d -p 27017:27017 --name mongo-bce mongo:7
```

### Tests automatiques

```bash
python scripts/test_pipeline.py      # config, State DB, parquet, MongoDB, DAG
python scripts/run_notebook_j2.py    # cellules notebook J2
```

### Exécution locale (sans Airflow)

```bash
cd ingestion_bronze

# Démo rapide (5000 entreprises + tables KBO)
python scripts/run_bronze_ingestion.py --step all --demo 5000

# Ingestion complète (~2M entreprises — long)
python scripts/run_bronze_ingestion.py --step all
```

### Airflow (interface web)

Sur Windows, Airflow tourne via **Docker** :

```bash
cd ingestion_bronze
docker compose -f docker-compose.airflow.yml up -d
# ou : powershell -File scripts/start_airflow.ps1
```

Ouvrir **http://localhost:8081** (port 8081 car 8080 est souvent occupe).

- **Login** : `admin` / `admin`
- **DAG** : `bce_ingestion_bronze_kbo`

Arreter : `docker compose -f docker-compose.airflow.yml down`

```bash
export AIRFLOW_HOME=./airflow_home
airflow dags test bce_ingestion_bronze_kbo 2026-06-29
```

## Branche Git (soumission)

```bash
git checkout -b INGESTION-BRONZE
git add ingestion_bronze/
git commit -m "Ingestion bronze KBO: MongoDB, State DB, DAG Airflow"
git push -u origin INGESTION-BRONZE
```

> La branche `main` ne contiendra que la dernière version stable en fin de TP.

## Jours 2-3 (à venir)

- DAG NBB : lire `enterprises` depuis MongoDB → delta State DB → PDF/CSV bronze
- DAG eJustice + Statuts notaire
- Passage Silver / Gold

## Configuration

Éditer `config/config.yaml` :

- `kbo.source_dir` : chemin vers `KboOpenData_*_Full`
- `mongodb.uri` : URI MongoDB
- `bronze.base_path` : stockage local (dev) ou montage HDFS
