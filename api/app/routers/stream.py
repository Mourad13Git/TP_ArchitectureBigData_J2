from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from api.app.services.db import get_cfg, get_statuts_col
from api.app.services.statuts_scraper import normalize_bce, stream_statuts_sse

router = APIRouter(prefix="/enterprise", tags=["stream"])


@router.get("/{bce}/statuts/stream")
async def statuts_stream(bce: str):
    cfg = get_cfg()
    statuts_col = get_statuts_col()
    bce_fmt = normalize_bce(bce)

    async def generator():
        async for msg in stream_statuts_sse(bce_fmt, cfg, statuts_col):
            yield msg

    return EventSourceResponse(generator())
