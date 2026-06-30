"""MongoDB — catalogue entreprises + State DB (meta)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator

from pymongo import ASCENDING, MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.database import Database


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"


@dataclass
class IngestionState:
    """Une ligne de la meta / State DB — un artefact téléchargé ou ingéré."""

    source: str  # kbo | nbb | ejustice | statuts
    bce_number: str | None  # None pour snapshots KBO globaux
    artifact_type: str  # csv_table | pdf | csv_nbb | full_snapshot | publication
    artifact_id: str  # nom table, deposit_id, numac…
    year: int | None = None
    status: ArtifactStatus = ArtifactStatus.PENDING
    hdfs_path: str | None = None
    local_path: str | None = None
    snapshot_id: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def state_key(self) -> str:
        parts = [self.source, self.artifact_type, self.artifact_id]
        if self.bce_number:
            parts.append(self.bce_number.replace(".", ""))
        if self.year is not None:
            parts.append(str(self.year))
        if self.snapshot_id:
            parts.append(self.snapshot_id)
        return "|".join(parts)

    def to_doc(self) -> dict:
        d = asdict(self)
        d["_id"] = self.state_key
        d["status"] = self.status.value
        return d


class MongoClientFactory:
    def __init__(self, uri: str, database: str):
        self.uri = uri
        self.database_name = database
        self._client: MongoClient | None = None

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
        return self._client

    @property
    def db(self) -> Database:
        return self.client[self.database_name]


class StateDB:
    """Meta DB : delta detection — ne pas re-télécharger ce qui est déjà done."""

    def __init__(self, collection: Collection):
        self.col = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.col.create_index([("source", ASCENDING), ("status", ASCENDING)])
        self.col.create_index([("bce_number", ASCENDING), ("year", ASCENDING)])
        self.col.create_index("updated_at")

    def get(self, state: IngestionState) -> dict | None:
        return self.col.find_one({"_id": state.state_key})

    def is_done(self, state: IngestionState) -> bool:
        doc = self.get(state)
        return doc is not None and doc.get("status") == ArtifactStatus.DONE.value

    def upsert(self, state: IngestionState) -> None:
        doc = state.to_doc()
        self.col.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    def mark_done(
        self,
        state: IngestionState,
        hdfs_path: str | None = None,
        local_path: str | None = None,
        **metadata,
    ) -> None:
        state.status = ArtifactStatus.DONE
        state.hdfs_path = hdfs_path
        state.local_path = local_path
        state.error_message = None
        state.metadata.update(metadata)
        state.updated_at = datetime.now(timezone.utc)
        self.upsert(state)

    def mark_error(self, state: IngestionState, error: str) -> None:
        state.status = ArtifactStatus.ERROR
        state.error_message = error
        state.updated_at = datetime.now(timezone.utc)
        self.upsert(state)

    def list_pending(self, source: str, limit: int = 100) -> list[dict]:
        return list(
            self.col.find({"source": source, "status": ArtifactStatus.PENDING.value}).limit(limit)
        )

    def snapshot_ingested(self, source: str, snapshot_id: str, artifact_id: str) -> bool:
        probe = IngestionState(
            source=source,
            bce_number=None,
            artifact_type="full_snapshot",
            artifact_id=artifact_id,
            snapshot_id=snapshot_id,
            status=ArtifactStatus.DONE,
        )
        return self.is_done(probe)


class EnterpriseRepository:
    """Catalogue MongoDB de toutes les entreprises belges (numéros BCE)."""

    def __init__(self, collection: Collection):
        self.col = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.col.create_index("bce_number", unique=True)
        self.col.create_index("status")
        self.col.create_index("juridical_form")

    def count(self) -> int:
        return self.col.count_documents({})

    def bulk_upsert(self, enterprises: list[dict]) -> int:
        if not enterprises:
            return 0
        ops = [
            UpdateOne(
                {"bce_number": e["bce_number"]},
                {"$set": e, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
            for e in enterprises
        ]
        result = self.col.bulk_write(ops, ordered=False)
        return result.upserted_count + result.modified_count

    def iter_bce_numbers(self, batch_size: int = 10_000, limit: int | None = None) -> Iterator[list[str]]:
        cursor = self.col.find({}, {"bce_number": 1, "_id": 0}).batch_size(batch_size)
        batch: list[str] = []
        n = 0
        for doc in cursor:
            batch.append(doc["bce_number"])
            n += 1
            if len(batch) >= batch_size:
                yield batch
                batch = []
            if limit and n >= limit:
                break
        if batch:
            yield batch

    def get_sample(self, n: int = 5) -> list[dict]:
        return list(self.col.find().limit(n))
