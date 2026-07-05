#!/usr/bin/env python3
"""Tests API J3 (health, search, enterprise, SSE)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TP_ROOT))

from fastapi.testclient import TestClient
from api.app.main import app


def main() -> int:
    client = TestClient(app)
    failed = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failed
        if cond:
            print(f"[OK] {name}")
        else:
            print(f"[FAIL] {name} {detail}")
            failed += 1

    check("health", client.get("/health").json().get("status") == "ok")

    search = client.get("/search?q=hotel")
    check("search", search.status_code == 200 and len(search.json()) >= 1, search.text)

    bce = "0339.226.816"
    r = client.get(f"/enterprise/{bce}")
    check("enterprise", r.status_code == 200, r.text)
    if r.status_code == 200:
        data = r.json()
        check("gold years", data.get("gold") and len(data["gold"]["years"]) >= 2)
        check("sankey", data.get("sankey") is not None)

    r2024 = client.get(f"/enterprise/{bce}?year=2024")
    if r2024.status_code == 200:
        check("sankey year", r2024.json().get("sankey", {}).get("year") == 2024)

    with client.stream("GET", f"/enterprise/{bce}/statuts/stream") as resp:
        check("sse status", resp.status_code == 200, str(resp.status_code))
        body = resp.read().decode("utf-8")
        check("sse body", "event:" in body and "data:" in body, body[:200])

    print(f"\nResultat: {5 - failed}/5 checks")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
