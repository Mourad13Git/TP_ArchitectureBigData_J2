"""Couche Gold hotel_gold — consolidation PCMN par entreprise."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from pymongo import ASCENDING, UpdateOne
from pymongo.collection import Collection

from src.db.mongodb import ArtifactStatus, StateDB
from src.pcmn_parser import parse_filing_file


def bce_nodot(enterprise_number: str) -> str:
    return enterprise_number.replace(".", "")


def nbb_enterprise_dir(bronze_dir: Path, nbb_subdir: str, enterprise_number: str) -> Path:
    """Equiv. HDFS {bce}/hbb/ — local: nbb/csvs/{bce}/."""
    primary = bronze_dir / nbb_subdir / bce_nodot(enterprise_number)
    return primary


def resolve_enterprise_csv_dirs(
    bronze_dir: Path,
    nbb_subdir: str,
    samples_dir: Path | None,
    enterprise_number: str,
) -> list[Path]:
    dirs = []
    primary = nbb_enterprise_dir(bronze_dir, nbb_subdir, enterprise_number)
    if primary.exists():
        dirs.append(primary)
    if samples_dir:
        sample = samples_dir / bce_nodot(enterprise_number)
        if sample.exists():
            dirs.append(sample)
    return dirs


def iter_filing_csvs(enterprise_dir: Path) -> Iterator[Path]:
    if not enterprise_dir.exists():
        return
    yield from sorted(enterprise_dir.rglob("*.csv"))


def build_gold_document(
    enterprise_number: str,
    filing_paths: list[Path],
    schema_type: str = "full",
) -> dict | None:
    years_map: dict[int, dict] = {}
    for path in filing_paths:
        record = parse_filing_file(path)
        if not record:
            continue
        year = record["year"]
        years_map[year] = record

    if not years_map:
        return None

    years = [years_map[y] for y in sorted(years_map)]
    return {
        "enterprise_number": enterprise_number,
        "years": years,
        "schema_type": schema_type,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


class HotelGoldRepository:
    def __init__(self, collection: Collection):
        self.col = collection
        self.col.create_index("enterprise_number", unique=True)
        self.col.create_index("last_updated")

    def count(self) -> int:
        return self.col.count_documents({})

    def upsert(self, doc: dict) -> None:
        self.col.update_one(
            {"enterprise_number": doc["enterprise_number"]},
            {"$set": doc},
            upsert=True,
        )

    def bulk_upsert(self, docs: list[dict]) -> int:
        if not docs:
            return 0
        ops = [
            UpdateOne({"enterprise_number": d["enterprise_number"]}, {"$set": d}, upsert=True)
            for d in docs
        ]
        result = self.col.bulk_write(ops, ordered=False)
        return result.upserted_count + result.modified_count

    def get(self, enterprise_number: str) -> dict | None:
        return self.col.find_one({"enterprise_number": enterprise_number}, {"_id": 0})

    def search_by_name(self, silver_col: Collection, query: str, limit: int = 20) -> list[dict]:
        regex = {"$regex": query, "$options": "i"}
        cursor = silver_col.find(
            {
                "$or": [
                    {"EnterpriseNumber": regex},
                    {"denominations.Denomination": regex},
                ]
            },
            {"_id": 0, "EnterpriseNumber": 1, "denominations": 1, "StatusLabel": 1},
        ).limit(limit)
        return list(cursor)


def list_done_hotellerie_bce(state_db: StateDB, limit: int = 0) -> list[str]:
    query = {
        "source": "nbb",
        "artifact_type": "enterprise",
        "artifact_id": "hotellerie",
        "status": ArtifactStatus.DONE.value,
    }
    cursor = state_db.col.find(query, {"bce_number": 1})
    if limit:
        cursor = cursor.limit(limit)
    numbers = []
    for doc in cursor:
        raw = doc.get("bce_number", "")
        if not raw:
            continue
        if len(raw) == 10:
            numbers.append(f"{raw[:4]}.{raw[4:7]}.{raw[7:]}")
        else:
            numbers.append(raw)
    return numbers


def iter_filing_csvs_from_dirs(dirs: list[Path]) -> Iterator[Path]:
    for d in dirs:
        yield from iter_filing_csvs(d)


def build_gold_for_enterprise(
    enterprise_number: str,
    bronze_dir: Path,
    nbb_subdir: str,
    samples_dir: Path | None = None,
) -> dict | None:
    dirs = resolve_enterprise_csv_dirs(bronze_dir, nbb_subdir, samples_dir, enterprise_number)
    paths = list(iter_filing_csvs_from_dirs(dirs))
    return build_gold_document(enterprise_number, paths)


def run_gold_pipeline(
    state_db: StateDB,
    gold_repo: HotelGoldRepository,
    bronze_dir: Path,
    nbb_subdir: str,
    samples_dir: Path | None = None,
    demo_limit: int = 0,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    enterprises = list_done_hotellerie_bce(state_db, limit=demo_limit or 0)
    if not enterprises and on_progress:
        on_progress("  Aucune entreprise NBB done — generation depuis CSV disponibles")
        enterprises = _enterprises_from_dirs(bronze_dir, nbb_subdir, samples_dir, demo_limit)

    total = 0
    batch: list[dict] = []
    for ent in enterprises:
        doc = build_gold_for_enterprise(ent, bronze_dir, nbb_subdir, samples_dir)
        if not doc:
            continue
        batch.append(doc)
        if len(batch) >= 100:
            gold_repo.bulk_upsert(batch)
            total += len(batch)
            batch = []
            if on_progress:
                on_progress(f"  hotel_gold: {total:,} documents...")

    if batch:
        gold_repo.bulk_upsert(batch)
        total += len(batch)

    if on_progress:
        on_progress(f"  OK hotel_gold: {total:,} documents")
    return total


def _enterprises_from_dirs(
    bronze_dir: Path, nbb_subdir: str, samples_dir: Path | None, limit: int
) -> list[str]:
    seen: set[str] = set()
    ents: list[str] = []
    for root in [bronze_dir / nbb_subdir, samples_dir] if samples_dir else [bronze_dir / nbb_subdir]:
        if not root or not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            bce = child.name
            if bce in seen:
                continue
            seen.add(bce)
            if len(bce) == 10:
                ents.append(f"{bce[:4]}.{bce[4:7]}.{bce[7:]}")
            else:
                ents.append(bce)
            if limit and len(ents) >= limit:
                return ents
    return ents
