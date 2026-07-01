"""Connexions runtime MongoDB / fallback fichier (scripts + Airflow)."""
from __future__ import annotations

from pathlib import Path

from src.db.file_enterprises import FileEnterpriseRepository
from src.db.file_state import FileStateDB
from src.db.mongodb import EnterpriseRepository, MongoClientFactory, StateDB


def get_stores(cfg: dict, on_warn=None):
    """MongoDB si disponible, sinon fallback fichiers locaux."""
    try:
        factory = MongoClientFactory(cfg["mongodb"]["uri"], cfg["mongodb"]["database"])
        factory.client.admin.command("ping")
        db = factory.db
        return (
            StateDB(db[cfg["mongodb"]["state_collection"]]),
            EnterpriseRepository(db[cfg["mongodb"]["enterprises_collection"]]),
            "mongodb",
        )
    except Exception:
        if on_warn:
            on_warn("[WARN] MongoDB indisponible - fallback fichiers locaux")
        base = Path(cfg["bronze"]["base_path"])
        return (
            FileStateDB(base / "_meta" / "ingestion_state.json"),
            FileEnterpriseRepository(base / "_meta" / "enterprises.json"),
            "file",
        )
