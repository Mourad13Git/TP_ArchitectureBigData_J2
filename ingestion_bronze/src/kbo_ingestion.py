"""Ingestion KBO Open Data → couche Bronze (Parquet)."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

import pandas as pd
import pyarrow.parquet as pq

from src.db.mongodb import ArtifactStatus, IngestionState, StateDB

KBO_TABLE_FILES = {
    "enterprise": "enterprise.csv",
    "denomination": "denomination.csv",
    "address": "address.csv",
    "activity": "activity.csv",
    "contact": "contact.csv",
    "establishment": "establishment.csv",
    "branch": "branch.csv",
    "code": "code.csv",
}


def read_kbo_meta(source_dir: Path) -> dict[str, str]:
    meta_path = source_dir / "meta.csv"
    if not meta_path.exists():
        return {}
    with open(meta_path, encoding="utf-8") as f:
        return {row["Variable"]: row["Value"] for row in csv.DictReader(f)}


def hdfs_path(hdfs_prefix: str, *parts: str) -> str:
    return "/".join([hdfs_prefix.rstrip("/"), *parts])


def ingest_kbo_table_to_bronze(
    table: str,
    source_dir: Path,
    bronze_dir: Path,
    hdfs_prefix: str,
    snapshot_id: str,
    state_db: StateDB,
    chunk_size: int = 500_000,
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """
    Convertit un CSV KBO en Parquet bronze (partitionné par snapshot).
    Met à jour la State DB — skip si déjà ingéré pour ce snapshot.
    """
    state = IngestionState(
        source="kbo",
        bce_number=None,
        artifact_type="full_snapshot",
        artifact_id=table,
        snapshot_id=snapshot_id,
    )
    if state_db.is_done(state):
        if on_progress:
            on_progress(f"  SKIP {table} (snapshot {snapshot_id} deja en State DB)")
        return state_db.get(state).get("local_path", "")

    csv_name = KBO_TABLE_FILES[table]
    csv_path = source_dir / csv_name
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    out_dir = bronze_dir / "kbo" / table / f"snapshot={snapshot_id}"
    parquet_files = list(out_dir.glob("*.parquet")) if out_dir.exists() else []
    if parquet_files and not state_db.is_done(state):
        total_rows = sum(pq.ParquetFile(p).metadata.num_rows for p in parquet_files)
        hpath = hdfs_path(hdfs_prefix, "kbo", table, f"snapshot={snapshot_id}")
        state_db.mark_done(
            state,
            hdfs_path=hpath,
            local_path=str(out_dir),
            rows=total_rows,
            format="parquet",
            backfilled=True,
        )
        if on_progress:
            on_progress(f"  SKIP {table} (bronze deja present, State DB mise a jour)")
        return str(out_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    state.status = ArtifactStatus.PENDING
    state_db.upsert(state)

    try:
        if table == "code":
            df = pd.read_csv(csv_path, dtype=str)
            part_path = out_dir / "part-00000.parquet"
            df.to_parquet(part_path, index=False)
            total_rows = len(df)
        else:
            total_rows = 0
            for i, chunk in enumerate(pd.read_csv(csv_path, dtype=str, chunksize=chunk_size)):
                part_path = out_dir / f"part-{i:05d}.parquet"
                chunk.to_parquet(part_path, index=False)
                total_rows += len(chunk)
                if on_progress and i % 5 == 0:
                    on_progress(f"    {table}: {total_rows:,} lignes...")

        bronze_rel = str(out_dir.relative_to(bronze_dir.parent) if bronze_dir.parent in out_dir.parents else out_dir)
        hpath = hdfs_path(hdfs_prefix, "kbo", table, f"snapshot={snapshot_id}")
        state_db.mark_done(
            state,
            hdfs_path=hpath,
            local_path=str(out_dir),
            rows=total_rows,
            format="parquet",
        )
        if on_progress:
            on_progress(f"  OK {table}: {total_rows:,} lignes -> {out_dir}")
        return str(out_dir)
    except Exception as e:
        state_db.mark_error(state, str(e))
        raise


def seed_enterprises_mongodb(
    source_dir: Path,
    enterprise_repo,
    batch_size: int = 10_000,
    demo_limit: int = 0,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    """Peuple MongoDB avec toutes les entreprises depuis enterprise.csv."""
    csv_path = source_dir / "enterprise.csv"
    total = 0
    batch: list[dict] = []

    for chunk in pd.read_csv(csv_path, dtype=str, chunksize=batch_size):
        for _, row in chunk.iterrows():
            if demo_limit and total + len(batch) >= demo_limit:
                break
            bce = row["EnterpriseNumber"]
            batch.append({
                "bce_number": bce,
                "bce_number_nodot": bce.replace(".", ""),
                "status": row.get("Status"),
                "juridical_situation": row.get("JuridicalSituation"),
                "type_of_enterprise": row.get("TypeOfEnterprise"),
                "juridical_form": row.get("JuridicalForm"),
                "start_date": row.get("StartDate"),
            })
            if len(batch) >= batch_size:
                enterprise_repo.bulk_upsert(batch)
                total += len(batch)
                batch = []
                if on_progress and total % 100_000 == 0:
                    on_progress(f"  MongoDB enterprises: {total:,}...")
        if demo_limit and total + len(batch) >= demo_limit:
            if demo_limit and total < demo_limit:
                batch = batch[: demo_limit - total]
            break
        if demo_limit and total >= demo_limit:
            break

    if batch:
        enterprise_repo.bulk_upsert(batch)
        total += len(batch)

    if on_progress:
        on_progress(f"  OK MongoDB: {total:,} entreprises indexees")
    return total
