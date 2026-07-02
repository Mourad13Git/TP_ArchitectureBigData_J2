from fastapi import APIRouter, HTTPException

from api.app.models.schemas import EnterpriseDetail
from api.app.services.db import get_cfg, get_gold_repo, get_silver_col
from api.app.services.kbopub import get_or_scrape_officers
from api.app.services.sankey import build_sankey
from api.app.services.db import get_officers_col

router = APIRouter(prefix="/enterprise", tags=["enterprise"])


def _normalize_bce(bce: str) -> str:
    raw = bce.replace(".", "").replace(" ", "")
    if len(raw) == 10:
        return f"{raw[:4]}.{raw[4:7]}.{raw[7:]}"
    return bce


@router.get("/{bce}", response_model=EnterpriseDetail)
def get_enterprise(bce: str, year: int | None = None):
    bce_fmt = _normalize_bce(bce)
    silver = get_silver_col().find_one({"EnterpriseNumber": bce_fmt}, {"_id": 0})
    if not silver:
        raise HTTPException(404, f"Entreprise {bce_fmt} introuvable dans enterprise_silver")

    gold_doc = get_gold_repo().get(bce_fmt)
    sankey = None
    if gold_doc and gold_doc.get("years"):
        years = gold_doc["years"]
        selected = next((y for y in years if y.get("year") == year), years[-1])
        sankey = build_sankey(selected)

    cfg = get_cfg()
    dirs = get_or_scrape_officers(bce_fmt, get_officers_col(), cfg)

    return EnterpriseDetail(
        enterprise_number=bce_fmt,
        silver=silver,
        gold=gold_doc,
        dirigeants=dirs,
        sankey=sankey,
    )
