"""Téléchargement NBB / eJustice / Statuts — squelette Jour 2-3."""
from __future__ import annotations

from pathlib import Path

import requests

from src.db.mongodb import ArtifactStatus, IngestionState, StateDB
from src.kbo_ingestion import hdfs_path


def download_nbb_deposit(
    bce_nodot: str,
    deposit: dict,
    bronze_dir: Path,
    hdfs_prefix: str,
    state_db: StateDB,
) -> bool:
    """
    Télécharge un dépôt NBB (PDF + CSV) si absent de la State DB.
    À appeler depuis le DAG Airflow (delta detection).
    """
    ref = deposit.get("referenceNumber") or deposit.get("id")
    year = deposit.get("exerciseYear") or deposit.get("fiscalYear")
    if not ref or not year:
        return False

    for artifact_type, url_key, subdir, ext in [
        ("pdf", "pdfUrl", "pdfs", "pdf"),
        ("csv_nbb", "csvUrl", "csvs", "csv"),
    ]:
        url = deposit.get(url_key) or deposit.get("accountingDataUrl")
        if not url and artifact_type == "csv_nbb":
            continue
        state = IngestionState(
            source="nbb",
            bce_number=bce_nodot,
            artifact_type=artifact_type,
            artifact_id=str(ref),
            year=int(year),
        )
        if state_db.is_done(state):
            continue
        state.status = ArtifactStatus.PENDING
        state_db.upsert(state)
        try:
            dest_dir = bronze_dir / "nbb" / subdir / bce_nodot
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{year}.{ext}"
            if url:
                r = requests.get(url, timeout=120, headers={"User-Agent": "BCE-Ingestion/1.0"})
                r.raise_for_status()
                dest.write_bytes(r.content)
            hpath = hdfs_path(hdfs_prefix, "nbb", subdir, bce_nodot, f"{year}.{ext}")
            state_db.mark_done(state, hdfs_path=hpath, local_path=str(dest))
        except Exception as e:
            state_db.mark_error(state, str(e))
            return False
    return True


def fetch_nbb_deposits_api(bce_nodot: str) -> list[dict]:
    """API publique NBB — peut retourner 403 hors cluster."""
    url = f"https://consult.cbso.nbb.be/api/enterprise/{bce_nodot}/deposits"
    try:
        r = requests.get(
            url,
            params={"page": 0, "size": 50, "sort": "depositDate,desc"},
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("content", data) if isinstance(data, dict) else []
    except Exception:
        return []
