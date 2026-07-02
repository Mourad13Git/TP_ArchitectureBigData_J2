"""Lecture filtree des tables KBO bronze (Parquet)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds


ENTITY_TABLES = {
    "denomination": "EntityNumber",
    "address": "EntityNumber",
    "activity": "EntityNumber",
    "contact": "EntityNumber",
}


def bronze_table_path(bronze_dir: Path, table: str, snapshot_id: str) -> Path:
    return bronze_dir / "kbo" / table / f"snapshot={snapshot_id}"


def read_enterprise_batch(
    bronze_dir: Path,
    snapshot_id: str,
    offset: int,
    limit: int,
) -> pd.DataFrame:
    path = bronze_table_path(bronze_dir, "enterprise", snapshot_id)
    files = sorted(path.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(path)
    frames = []
    seen = 0
    for file in files:
        df = pd.read_parquet(file)
        if seen + len(df) <= offset:
            seen += len(df)
            continue
        start = max(0, offset - seen)
        end = start + (limit - sum(len(f) for f in frames))
        frames.append(df.iloc[start:end])
        seen += len(df)
        if sum(len(f) for f in frames) >= limit:
            break
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).head(limit)


def read_related_rows(
    bronze_dir: Path,
    table: str,
    snapshot_id: str,
    entity_numbers: list[str],
) -> pd.DataFrame:
    if not entity_numbers:
        return pd.DataFrame()
    path = bronze_table_path(bronze_dir, table, snapshot_id)
    if not path.exists():
        return pd.DataFrame()
    id_col = ENTITY_TABLES[table]
    dataset = ds.dataset(path, format="parquet")
    table_data = dataset.to_table(filter=ds.field(id_col).isin(entity_numbers))
    if table_data.num_rows == 0:
        return pd.DataFrame(columns=table_data.schema.names)
    return table_data.to_pandas()


def group_by_entity(df: pd.DataFrame, id_col: str) -> dict[str, list[dict]]:
    if df.empty:
        return {}
    grouped: dict[str, list[dict]] = {}
    for entity, group in df.groupby(id_col, sort=False):
        grouped[str(entity)] = group.where(pd.notna(group), None).to_dict(orient="records")
    return grouped
