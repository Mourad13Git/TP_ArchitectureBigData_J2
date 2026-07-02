"""Telechargement NBB CBSO — depots financiers hotellerie."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import requests

from src.db.mongodb import ArtifactStatus, IngestionState, StateDB
from src.kbo_ingestion import hdfs_path


class NbbRateLimitError(Exception):
    pass


class NbbForbiddenError(Exception):
    pass


def _request_json(url: str, params: dict | None = None, max_retries: int = 5) -> dict | list:
    headers = {"Accept": "application/json", "User-Agent": "BCE-Ingestion/1.0"}
    for attempt in range(max_retries):
        response = requests.get(url, params=params, headers=headers, timeout=60)
        if response.status_code == 403:
            raise NbbForbiddenError(f"403 Forbidden: {url}")
        if response.status_code == 429:
            wait = min(60, 2 ** attempt)
            time.sleep(wait)
            if attempt == max_retries - 1:
                raise NbbRateLimitError(f"429 sur {url}")
            continue
        if response.status_code != 200:
            return {}
        return response.json()
    return {}


def _request_bytes(url: str, max_retries: int = 5) -> bytes:
    headers = {"Accept": "*/*", "User-Agent": "BCE-Ingestion/1.0"}
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers, timeout=120)
        if response.status_code == 403:
            raise NbbForbiddenError(f"403 Forbidden: {url}")
        if response.status_code == 429:
            wait = min(60, 2 ** attempt)
            time.sleep(wait)
            if attempt == max_retries - 1:
                raise NbbRateLimitError(f"429 sur {url}")
            continue
        response.raise_for_status()
        return response.content
    return b""


def _year_from_filing(filing: dict) -> int | None:
    for key in ("accountingYearEndDate", "exerciseYear", "fiscalYear", "year"):
        value = filing.get(key)
        if value is None:
            continue
        text = str(value)
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).year
        except ValueError:
            continue
    return None


def _reference_from_filing(filing: dict) -> str | None:
    for key in ("reference", "referenceNumber", "id", "depositId"):
        value = filing.get(key)
        if value:
            return str(value)
    return None


def fetch_nbb_filings_api(bce_nodot: str, base_url: str) -> list[dict]:
    url = f"{base_url.rstrip('/')}/api/enterprises/{bce_nodot}/filings"
    data = _request_json(url)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("content", data.get("filings", []))
    return []


def fetch_nbb_deposits_api(bce_nodot: str) -> list[dict]:
    url = f"https://consult.cbso.nbb.be/api/enterprise/{bce_nodot}/deposits"
    data = _request_json(url, params={"page": 0, "size": 50, "sort": "depositDate,desc"})
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("content", [])
    return []


def list_filings_since_2021(bce_nodot: str, cfg: dict) -> list[dict]:
    min_year = int(cfg["nbb"].get("min_year", 2021))
    filings = fetch_nbb_filings_api(bce_nodot, cfg["nbb"]["base_url"])
    if not filings:
        filings = fetch_nbb_deposits_api(bce_nodot)

    selected = []
    for filing in filings:
        year = _year_from_filing(filing)
        if year is None or year < min_year:
            continue
        reference = _reference_from_filing(filing)
        if not reference:
            continue
        selected.append({**filing, "_year": year, "_reference": reference})
    return selected


def download_filing_csv(
    bce_nodot: str,
    filing: dict,
    bronze_dir: Path,
    hdfs_prefix: str,
    state_db: StateDB,
    cfg: dict,
) -> bool:
    reference = filing["_reference"]
    year = filing["_year"]
    state = IngestionState(
        source="nbb",
        bce_number=bce_nodot,
        artifact_type="csv_nbb",
        artifact_id=reference,
        year=year,
    )
    if state_db.is_done(state):
        return True

    state.status = ArtifactStatus.PENDING
    state_db.upsert(state)

    url = cfg["nbb"]["api_filing_document"].format(reference=reference)
    try:
        content = _request_bytes(url)
        if not content:
            csv_url = filing.get("csvUrl") or filing.get("accountingDataUrl")
            if csv_url:
                content = _request_bytes(csv_url)
        if not content:
            state_db.mark_error(state, "CSV introuvable")
            return False

        dest_dir = bronze_dir / "nbb" / "csvs" / bce_nodot / str(year)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{reference}.csv"
        dest.write_bytes(content)
        hpath = hdfs_path(hdfs_prefix, "nbb", "csvs", bce_nodot, str(year), f"{reference}.csv")
        state_db.mark_done(state, hdfs_path=hpath, local_path=str(dest))
        return True
    except (NbbRateLimitError, NbbForbiddenError):
        raise
    except Exception as exc:
        state_db.mark_error(state, str(exc))
        return False


def scrape_hotellerie_enterprise(
    bce_nodot: str,
    bronze_dir: Path,
    hdfs_prefix: str,
    state_db: StateDB,
    cfg: dict,
) -> tuple[bool, int]:
    enterprise_state = IngestionState(
        source="nbb",
        bce_number=bce_nodot,
        artifact_type="enterprise",
        artifact_id="hotellerie",
    )
    if state_db.is_done(enterprise_state):
        existing = state_db.get(enterprise_state) or {}
        return True, int(existing.get("metadata", {}).get("filings_count", 0))

    state_db.mark_in_progress(enterprise_state)
    try:
        filings = list_filings_since_2021(bce_nodot, cfg)
    except NbbForbiddenError as exc:
        state_db.mark_error(enterprise_state, str(exc))
        return False, 0

    downloaded = 0
    for filing in filings:
        delay = float(cfg["nbb"].get("request_delay_sec", 0.5))
        if delay > 0:
            time.sleep(delay)
        if download_filing_csv(bce_nodot, filing, bronze_dir, hdfs_prefix, state_db, cfg):
            downloaded += 1

    enterprise_state.status = ArtifactStatus.DONE
    enterprise_state.metadata = {"filings_count": downloaded}
    state_db.mark_done(enterprise_state, filings_count=downloaded)
    return True, downloaded


def scrape_hotellerie_pending(
    state_db: StateDB,
    bronze_dir: Path,
    hdfs_prefix: str,
    cfg: dict,
    limit: int = 50,
    on_progress=None,
) -> dict:
    pending = state_db.list_pending("nbb", limit=limit)
    stats = {"processed": 0, "done": 0, "errors": 0, "filings": 0, "rate_limited": False, "forbidden": False}

    for item in pending:
        if item.get("artifact_type") != "enterprise":
            continue
        bce = item.get("bce_number")
        if not bce:
            continue
        try:
            ok, count = scrape_hotellerie_enterprise(bce, bronze_dir, hdfs_prefix, state_db, cfg)
            stats["processed"] += 1
            stats["filings"] += count
            if ok:
                stats["done"] += 1
            else:
                stats["errors"] += 1
                err_doc = state_db.get(
                    IngestionState(
                        source="nbb",
                        bce_number=bce,
                        artifact_type="enterprise",
                        artifact_id="hotellerie",
                    )
                )
                if err_doc and "403" in str(err_doc.get("error_message", "")):
                    stats["forbidden"] = True
            if on_progress:
                on_progress(f"  NBB {bce}: {count} depots")
        except NbbRateLimitError:
            stats["rate_limited"] = True
            if on_progress:
                on_progress(f"  [429] rate limit atteint apres {stats['processed']} entreprises")
            break
        except NbbForbiddenError as exc:
            stats["errors"] += 1
            stats["forbidden"] = True
            if on_progress:
                on_progress(f"  [403] API NBB inaccessible: {exc}")
            break

    return stats


def download_nbb_deposit(
    bce_nodot: str,
    deposit: dict,
    bronze_dir: Path,
    hdfs_prefix: str,
    state_db: StateDB,
    cfg: dict | None = None,
) -> bool:
    """Compatibilite ancienne API deposits."""
    ref = deposit.get("referenceNumber") or deposit.get("id")
    year = deposit.get("exerciseYear") or deposit.get("fiscalYear")
    if not ref or not year:
        return False
    filing = {"_reference": str(ref), "_year": int(year), **deposit}
    if cfg is None:
        cfg = {
            "nbb": {
                "api_filing_document": "https://consult.cbso.nbb.be/api/filings/{reference}/document"
            }
        }
    return download_filing_csv(bce_nodot, filing, bronze_dir, hdfs_prefix, state_db, cfg)
