#!/usr/bin/env python3
"""Seed demo enterprise_silver + hotel_gold pour tests API locaux."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.db.mongodb import EnterpriseDocumentRepository
from src.gold_transform import HotelGoldRepository, build_gold_for_enterprise, run_gold_pipeline
from src.runtime import get_silver_repos, require_mongo_db

BCE = "0339.226.816"


def main() -> None:
    cfg = load_config()
    db = require_mongo_db(cfg)
    _, silver_repo, state_db = get_silver_repos(cfg, db)
    gold_repo = HotelGoldRepository(db[cfg["mongodb"]["gold_collection"]])

    silver_repo.bulk_upsert([{
        "EnterpriseNumber": BCE,
        "Status": "AC",
        "StatusLabel": "Actif",
        "JuridicalForm": "610",
        "JuridicalFormLabel": "Societe a responsabilite limitee",
        "TypeOfEnterprise": "2",
        "denominations": [{"TypeOfDenomination": "1", "Denomination": "Hotel Demo Bruxelles", "Language": "1"}],
        "addresses": [{"TypeOfAddress": "REGO", "StreetFR": "Rue de la Loi", "HouseNumber": "1", "Zipcode": "1000", "MunicipalityFR": "Bruxelles"}],
        "activities": [{"NaceCode": "55100", "NaceVersion": "2025", "NaceLabel": "Hotels et hebergement similaire", "Classification": "MAIN", "ClassificationLabel": "Activite principale"}],
    }])

    run_gold_pipeline(
        state_db=state_db,
        gold_repo=gold_repo,
        bronze_dir=Path(cfg["bronze"]["base_path"]),
        nbb_subdir=cfg["gold"]["nbb_bronze_subdir"],
        samples_dir=ROOT / cfg["gold"]["samples_nbb_dir"],
        demo_limit=1,
        on_progress=print,
    )
    print("Demo seed OK —", BCE)


if __name__ == "__main__":
    main()
