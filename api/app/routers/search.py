from fastapi import APIRouter, Query

from api.app.models.schemas import SearchResult
from api.app.services.db import get_gold_repo, get_silver_col

router = APIRouter(prefix="/search", tags=["search"])


def _primary_name(doc: dict) -> str:
    denoms = doc.get("denominations") or []
    for d in denoms:
        if str(d.get("TypeOfDenomination", "")) == "1":
            return d.get("Denomination") or doc.get("EnterpriseNumber", "")
    return denoms[0].get("Denomination") if denoms else doc.get("EnterpriseNumber", "")


@router.get("", response_model=list[SearchResult])
def search(q: str = Query(..., min_length=1), limit: int = 50):
    silver = get_silver_col()
    gold_repo = get_gold_repo()
    regex = {"$regex": q, "$options": "i"}
    cursor = silver.find(
        {
            "$or": [
                {"EnterpriseNumber": regex},
                {"denominations.Denomination": regex},
                {"addresses.MunicipalityFR": regex},
                {"addresses.MunicipalityNL": regex},
                {"addresses.StreetFR": regex},
                {"activities.NaceLabel": regex},
            ]
        },
        {"_id": 0},
    ).limit(limit)
    results = []
    for doc in cursor:
        bce = doc["EnterpriseNumber"]
        gold = gold_repo.get(bce)
        years = (gold or {}).get("years") or []
        latest = years[-1] if years else {}
        results.append(
            SearchResult(
                enterprise_number=bce,
                name=_primary_name(doc),
                status=doc.get("StatusLabel") or doc.get("Status"),
                has_gold=bool(years),
                latest_ca=latest.get("chiffre_affaires"),
                years_count=len(years),
            )
        )
    results.sort(key=lambda r: (not r.has_gold, r.name))
    return results
