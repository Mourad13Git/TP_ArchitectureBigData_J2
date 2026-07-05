"""Lecture ciblée d'entreprises KBO par numéro BCE (CSV full dump)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd

from src.enterprise_finale import RELATED_TABLES, build_enterprise_document
from src.kbo_ingestion import KBO_TABLE_FILES

CHUNK = 250_000


def _normalize_bce_list(bce_numbers: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in bce_numbers:
        text = str(raw).strip().replace(" ", "")
        if len(text) == 10 and text.isdigit():
            out.add(f"{text[:4]}.{text[4:7]}.{text[7:]}")
        elif "." in text:
            out.add(text)
        else:
            out.add(text)
    return out


def _read_csv_chunks(path: Path, usecols: list[str] | None = None) -> Iterator[pd.DataFrame]:
    kwargs: dict = {"dtype": str, "chunksize": CHUNK}
    if usecols:
        kwargs["usecols"] = usecols
    yield from pd.read_csv(path, **kwargs)


def load_enterprises_from_kbo(
    source_dir: Path,
    bce_numbers: list[str],
) -> list[dict]:
    """Charge enterprise + tables liées pour une liste de BCE depuis les CSV KBO."""
    targets = _normalize_bce_list(bce_numbers)
    if not targets:
        return []

    ent_path = source_dir / KBO_TABLE_FILES["enterprise"]
    if not ent_path.exists():
        raise FileNotFoundError(ent_path)

    found_rows: list[dict] = []
    remaining = set(targets)

    for chunk in _read_csv_chunks(ent_path):
        chunk["EnterpriseNumber"] = chunk["EnterpriseNumber"].astype(str)
        hits = chunk[chunk["EnterpriseNumber"].isin(remaining)]
        for _, row in hits.iterrows():
            found_rows.append(row.to_dict())
            remaining.discard(str(row["EnterpriseNumber"]))
        if not remaining:
            break

    if not found_rows:
        return []

    bce_list = [str(r["EnterpriseNumber"]) for r in found_rows]
    related: dict[str, dict[str, list[dict]]] = {table: {} for table in RELATED_TABLES}

    for table in RELATED_TABLES:
        path = source_dir / KBO_TABLE_FILES[table]
        if not path.exists():
            continue
        id_col = "EntityNumber"
        for chunk in _read_csv_chunks(path):
            if id_col not in chunk.columns:
                continue
            chunk[id_col] = chunk[id_col].astype(str)
            hits = chunk[chunk[id_col].isin(bce_list)]
            for bce, group in hits.groupby(id_col, sort=False):
                related[table].setdefault(
                    str(bce),
                    group.where(pd.notna(group), None).to_dict(orient="records"),
                )

    documents = []
    for row in found_rows:
        bce = str(row["EnterpriseNumber"])
        documents.append(
            build_enterprise_document(
                row,
                related["denomination"].get(bce, []),
                related["address"].get(bce, []),
                related["activity"].get(bce, []),
                related["contact"].get(bce, []),
            )
        )
    return documents
