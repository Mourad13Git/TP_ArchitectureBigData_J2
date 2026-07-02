"""Parsing CSV PCMN NBB (code_pcmn;valeur)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PCMN_FIELDS = {
    "chiffre_affaires": ["70"],
    "achats": ["60"],
    "variation_stocks": ["71"],
    "ebit": ["9901"],
    "resultat_net": ["9904"],
    "tresorerie": ["54", "55"],
    "dettes_financieres": ["17", "43"],
    "fonds_propres": ["10", "11", "12", "13", "14", "15"],
    "capital_souscrit": ["100"],
}


def parse_pcmn_csv(path: Path) -> dict[str, float]:
    """Lit un CSV NBB et retourne les montants par code PCMN brut."""
    try:
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    except Exception:
        df = pd.read_csv(path, dtype=str)

    cols = {c.lower(): c for c in df.columns}
    code_col = next((cols[k] for k in cols if "code" in k or "pcmn" in k), df.columns[0])
    val_col = next(
        (cols[k] for k in cols if k in ("valeur", "value", "amount", "montant") or "val" in k),
        df.columns[-1],
    )

    amounts: dict[str, float] = {}
    for _, row in df.iterrows():
        code = str(row[code_col]).strip()
        if not code or code.lower() == "nan":
            continue
        try:
            val = float(str(row[val_col]).replace(",", ".").replace(" ", "").replace("\xa0", ""))
        except (ValueError, TypeError):
            continue
        amounts[code] = amounts.get(code, 0.0) + val
    return amounts


def sum_pcmn_codes(amounts: dict[str, float], codes: list[str]) -> float:
    total = 0.0
    for code in codes:
        if code in amounts:
            total += amounts[code]
        else:
            for key, value in amounts.items():
                if key.startswith(code):
                    total += value
    return total


def extract_fields(amounts: dict[str, float]) -> dict[str, float]:
    return {field: sum_pcmn_codes(amounts, codes) for field, codes in PCMN_FIELDS.items()}


def compute_ratios(fields: dict[str, float]) -> dict[str, float | None]:
    ca = fields.get("chiffre_affaires", 0.0)
    achats = fields.get("achats", 0.0)
    var_stocks = fields.get("variation_stocks", 0.0)
    rn = fields.get("resultat_net", 0.0)
    fp = fields.get("fonds_propres", 0.0)
    tres = fields.get("tresorerie", 0.0)
    dettes = fields.get("dettes_financieres", 0.0)

    marge_brute = ca - achats + var_stocks

    def pct(num: float, den: float) -> float | None:
        return round(num / den * 100, 2) if den else None

    def ratio(num: float, den: float) -> float | None:
        return round(num / den, 4) if den else None

    return {
        "marge_brute": round(marge_brute, 2),
        "marge_nette_pct": pct(rn, ca),
        "roe_pct": pct(rn, fp),
        "ratio_liquidite": ratio(tres, dettes),
        "taux_endettement_pct": pct(dettes, fp),
    }


def year_from_filing(path: Path) -> int | None:
    parent = path.parent.name
    if parent.isdigit() and len(parent) == 4:
        return int(parent)
    for part in path.stem.split("-"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return None


def build_year_record(amounts: dict[str, float], year: int) -> dict:
    fields = extract_fields(amounts)
    ratios = compute_ratios(fields)
    return {
        "year": year,
        **fields,
        "ratios": ratios,
    }


def parse_filing_file(path: Path) -> dict | None:
    year = year_from_filing(path)
    if year is None:
        return None
    amounts = parse_pcmn_csv(path)
    if not amounts:
        return None
    return build_year_record(amounts, year)
