#!/usr/bin/env python3
"""Tests Gold PCMN parser."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pcmn_parser import build_year_record, parse_pcmn_csv


def test_parse_and_ratios() -> None:
    csv_content = """code_pcmn;valeur
70;1000000
60;400000
71;50000
9901;120000
9904;80000
54;150000
55;50000
17;100000
43;50000
10;300000
15;200000
100;100000
"""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        path = Path(f.name)

    amounts = parse_pcmn_csv(path)
    record = build_year_record(amounts, 2024)
    path.unlink()

    assert record["chiffre_affaires"] == 1_000_000
    assert record["ratios"]["marge_brute"] == 650_000  # 1M - 400k + 50k
    assert record["ratios"]["marge_nette_pct"] == 8.0
    print("[OK] parse_pcmn + ratios")


def main() -> int:
    try:
        test_parse_and_ratios()
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1
    print("Resultat: 1/1 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
