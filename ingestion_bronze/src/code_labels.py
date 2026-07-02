"""Decodage des codes KBO via code.csv / bronze Parquet."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds


class CodeLabelResolver:
    """Map (Category, Code) -> description FR."""

    def __init__(self, code_map: dict[tuple[str, str], str]):
        self._map = code_map

    @classmethod
    def from_csv(cls, source_dir: Path) -> CodeLabelResolver:
        path = source_dir / "code.csv"
        df = pd.read_csv(path, dtype=str)
        return cls.from_dataframe(df)

    @classmethod
    def from_parquet(cls, bronze_dir: Path, snapshot_id: str) -> CodeLabelResolver:
        path = bronze_dir / "kbo" / "code" / f"snapshot={snapshot_id}"
        if not path.exists():
            raise FileNotFoundError(path)
        table = ds.dataset(path, format="parquet").to_table()
        df = table.to_pandas()
        return cls.from_dataframe(df)

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> CodeLabelResolver:
        fr = df[df["Language"] == "FR"]
        code_map = {
            (str(row.Category), str(row.Code).strip()): str(row.Description)
            for row in fr.itertuples(index=False)
        }
        return cls(code_map)

    def label(self, category: str, code: str | None) -> str:
        if code is None or str(code).strip() == "":
            return ""
        return self._map.get((category, str(code).strip()), str(code).strip())

    def nace_label(self, nace_version: str, nace_code: str) -> str:
        version = str(nace_version).strip()
        code = str(nace_code).strip()
        for category in (f"Nace{version}", "Nace2008", "Nace2025", "Nace2003"):
            label = self.label(category, code)
            if label != code:
                return label
        return code
