"""Connexion MongoDB partagee API <-> ingestion_bronze."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pymongo.database import Database

ROOT = Path(__file__).resolve().parents[3] / "ingestion_bronze"
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.gold_transform import HotelGoldRepository
from src.runtime import require_mongo_db


@lru_cache
def get_cfg() -> dict:
    return load_config(ROOT / "config" / "config.yaml")


def get_db() -> Database:
    return require_mongo_db(get_cfg())


def get_gold_repo() -> HotelGoldRepository:
    cfg = get_cfg()
    return HotelGoldRepository(get_db()[cfg["mongodb"]["gold_collection"]])


def get_silver_col():
    cfg = get_cfg()
    return get_db()[cfg["mongodb"]["silver_collection"]]


def get_officers_col():
    cfg = get_cfg()
    return get_db()[cfg["mongodb"]["officers_collection"]]


def get_statuts_col():
    cfg = get_cfg()
    return get_db()[cfg["mongodb"]["statuts_collection"]]


def get_ejustice_col():
    cfg = get_cfg()
    return get_db()[cfg["mongodb"]["ejustice_collection"]]


def get_contacts_col():
    cfg = get_cfg()
    return get_db()[cfg["mongodb"]["contacts_collection"]]
