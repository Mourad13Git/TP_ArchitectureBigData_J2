#!/usr/bin/env python3
"""Lance l'API FastAPI."""
import uvicorn

from api.app.services.db import get_cfg

if __name__ == "__main__":
    cfg = get_cfg()
    uvicorn.run(
        "api.app.main:app",
        host=cfg["api"]["host"],
        port=int(cfg["api"]["port"]),
        reload=True,
    )
