"""State DB fichier JSON — fallback local sans MongoDB."""
from __future__ import annotations

import json
from pathlib import Path

from src.db.mongodb import ArtifactStatus, IngestionState, StateDB


class FileStateDB(StateDB):
    """Même interface que StateDB, persistance JSON locale."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict] = {}
        if self.path.exists():
            self._cache = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def col(self):
        raise NotImplementedError("FileStateDB n'expose pas col")

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._cache, indent=2, default=str), encoding="utf-8")

    def get(self, state: IngestionState) -> dict | None:
        return self._cache.get(state.state_key)

    def is_done(self, state: IngestionState) -> bool:
        doc = self.get(state)
        return doc is not None and doc.get("status") == ArtifactStatus.DONE.value

    def upsert(self, state: IngestionState) -> None:
        self._cache[state.state_key] = state.to_doc()
        self._save()

    def list_pending(self, source: str, limit: int = 100) -> list[dict]:
        return [d for d in self._cache.values() if d.get("source") == source and d.get("status") == "pending"][:limit]
