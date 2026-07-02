#!/usr/bin/env python3
"""Tests unitaires Silver + hotellerie (sans appels NBB reseau)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.code_labels import CodeLabelResolver
from src.config import load_config
from src.silver_transform import (
    dedupe_activities,
    filter_rego_addresses,
    normalize_date,
    sort_denominations,
    to_silver_document,
)


def test_normalize_date() -> None:
    assert normalize_date("02-01-2021") == "2021-01-02"
    assert normalize_date("16-03-1880") == "1880-03-16"
    print("[OK] normalize_date")


def test_dedupe_activities() -> None:
    acts = [
        {"NaceCode": "62020", "Classification": "MAIN", "NaceVersion": "2008"},
        {"NaceCode": "62020", "Classification": "MAIN", "NaceVersion": "2025"},
        {"NaceCode": "70220", "Classification": "MAIN", "NaceVersion": "2008"},
        {"NaceCode": "70200", "Classification": "MAIN", "NaceVersion": "2025"},
        {"NaceCode": "62020", "Classification": "SECO", "NaceVersion": "2008"},
    ]
    out = dedupe_activities(acts)
    assert len(out) == 4
    print("[OK] dedupe_activities")


def test_filter_rego_and_denomination() -> None:
    addresses = [
        {"TypeOfAddress": "ABBR", "StreetFR": "A"},
        {"TypeOfAddress": "REGO", "StreetFR": "B"},
    ]
    assert len(filter_rego_addresses(addresses)) == 1
    denoms = [
        {"TypeOfDenomination": "2", "Denomination": "Alias"},
        {"TypeOfDenomination": "1", "Denomination": "Officiel"},
    ]
    assert sort_denominations(denoms)[0]["Denomination"] == "Officiel"
    print("[OK] adresse REGO + denomination principale")


def test_silver_labels() -> None:
    cfg = load_config()
    labels = CodeLabelResolver.from_csv(Path(cfg["kbo"]["source_dir"]))
    doc = {
        "EnterpriseNumber": "0878.065.378",
        "Status": "AC",
        "JuridicalForm": "610",
        "StartDate": "02-01-2021",
        "addresses": [{"TypeOfAddress": "REGO"}],
        "denominations": [],
        "activities": [{"NaceCode": "55100", "Classification": "MAIN", "NaceVersion": "2025"}],
    }
    silver = to_silver_document(doc, labels)
    assert silver["StartDate"] == "2021-01-02"
    assert silver["StatusLabel"]
    assert silver["activities"][0]["NaceLabel"]
    print("[OK] silver labels")


def main() -> int:
    tests = [
        test_normalize_date,
        test_dedupe_activities,
        test_filter_rego_and_denomination,
        test_silver_labels,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc}")
            failed += 1
    print(f"\nResultat: {len(tests) - failed}/{len(tests)} OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
