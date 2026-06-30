"""Chargement de la configuration YAML."""
from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_PATH = _ROOT / "config" / "config.yaml"


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or _CONFIG_PATH
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
    return cfg
