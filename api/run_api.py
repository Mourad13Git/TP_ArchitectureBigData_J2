#!/usr/bin/env python3
"""Lance l'API FastAPI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Racine du projet (TP1) — requis pour `import api.*`
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REQUIRED = (
    "fastapi",
    "uvicorn",
    "pymongo",
    "yaml",
    "requests",
    "bs4",
    "sse_starlette",
)


def check_dependencies() -> None:
    missing = []
    for name in REQUIRED:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print("Dependances API manquantes:", ", ".join(missing))
        print(f"Installez-les avec:\n  {sys.executable} -m pip install -r api/requirements.txt")
        raise SystemExit(1)


if __name__ == "__main__":
    check_dependencies()

    import uvicorn

    from api.app.services.db import get_cfg

    cfg = get_cfg()
    # reload=False evite les soucis de sous-processus sous Windows
    uvicorn.run(
        "api.app.main:app",
        host=cfg["api"]["host"],
        port=int(cfg["api"]["port"]),
        reload=False,
    )
