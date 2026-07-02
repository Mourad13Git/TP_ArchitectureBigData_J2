import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

TP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TP_ROOT))

from api.app.routers import enterprise, search, stream
from api.app.services.db import get_cfg

cfg = get_cfg()

app = FastAPI(title="BCE Hotel Gold API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg["api"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(enterprise.router)
app.include_router(stream.router)


@app.get("/health")
def health():
    return {"status": "ok"}
