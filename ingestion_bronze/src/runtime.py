"""Connexions runtime MongoDB / fallback fichier (scripts + Airflow)."""
from __future__ import annotations

from pathlib import Path

from src.db.file_enterprises import FileEnterpriseRepository
from src.db.file_state import FileStateDB
from src.db.mongodb import EnterpriseDocumentRepository, EnterpriseRepository, MongoClientFactory, StateDB


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


def require_mongo_db(cfg: dict, on_warn=None):
    """MongoDB obligatoire pour la couche Silver."""
    try:
        factory = MongoClientFactory(cfg["mongodb"]["uri"], cfg["mongodb"]["database"])
        factory.client.admin.command("ping")
        return factory.db
    except Exception as exc:
        if on_warn:
            on_warn(f"[ERROR] MongoDB requis: {exc}")
        raise SystemExit(1) from exc


def get_silver_repos(cfg: dict, db=None):
    database = require_mongo_db(cfg) if db is None else db
    finale = EnterpriseDocumentRepository(database[cfg["mongodb"]["finale_collection"]])
    silver = EnterpriseDocumentRepository(database[cfg["mongodb"]["silver_collection"]])
    state_db = StateDB(database[cfg["mongodb"]["state_collection"]])
    return finale, silver, state_db
