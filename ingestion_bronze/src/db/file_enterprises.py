"""Catalogue entreprises en JSON — fallback sans MongoDB."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class FileEnterpriseRepository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            self._data = {e["bce_number"]: e for e in json.loads(self.path.read_text(encoding="utf-8"))}

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(list(self._data.values()), indent=2, default=str),
            encoding="utf-8",
        )

    def count(self) -> int:
        return len(self._data)

    def bulk_upsert(self, enterprises: list[dict]) -> int:
        n = 0
        for e in enterprises:
            if e["bce_number"] not in self._data:
                e.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                n += 1
            self._data[e["bce_number"]] = e
        self._save()
        return n

    def iter_bce_numbers(self, batch_size: int = 10_000, limit: int | None = None) -> Iterator[list[str]]:
        keys = list(self._data.keys())
        if limit:
            keys = keys[:limit]
        for i in range(0, len(keys), batch_size):
            yield keys[i : i + batch_size]

    def get_sample(self, n: int = 5) -> list[dict]:
        return list(self._data.values())[:n]
