"""Chargement de la configuration YAML."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = _ROOT / "config" / "config.yaml"


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or Path(os.environ.get("BCE_CONFIG_PATH", _CONFIG_PATH))
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Resoudre chemins relatifs depuis ingestion_bronze/
    root = cfg_path.parent.parent
    kbo_dir = Path(cfg["kbo"]["source_dir"])
    if not kbo_dir.is_absolute():
        cfg["kbo"]["source_dir"] = str((root / kbo_dir).resolve())
    bronze = Path(cfg["bronze"]["base_path"])
    if not bronze.is_absolute():
        cfg["bronze"]["base_path"] = str((root / bronze).resolve())

    # Surcharges Docker / cluster (voir docker-compose.airflow.yml)
    if uri := os.environ.get("BCE_MONGODB_URI"):
        cfg["mongodb"]["uri"] = uri
    if kbo := os.environ.get("BCE_KBO_SOURCE_DIR"):
        cfg["kbo"]["source_dir"] = kbo
    if demo := os.environ.get("BCE_DEMO_LIMIT_ENTERPRISES"):
        cfg["ingestion"]["demo_limit_enterprises"] = int(demo)
    if tables := os.environ.get("BCE_KBO_TABLES"):
        cfg["kbo"]["tables"] = [t.strip() for t in tables.split(",") if t.strip()]

    return cfg
