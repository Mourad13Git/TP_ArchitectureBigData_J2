"""Utilitaires Sankey compte de resultats."""
from __future__ import annotations

from api.app.models.schemas import SankeyData, SankeyNode


def build_sankey(year_data: dict) -> SankeyData:
    ca = float(year_data.get("chiffre_affaires") or 0)
    achats = float(year_data.get("achats") or 0)
    var_stocks = float(year_data.get("variation_stocks") or 0)
    rn = float(year_data.get("resultat_net") or 0)
    marge_brute = ca - achats + var_stocks

    year = int(year_data.get("year", 0))
    nodes = [
        SankeyNode(label="CA", value=ca),
        SankeyNode(label="Marge brute", value=max(marge_brute, 0)),
        SankeyNode(label="Resultat net", value=rn),
    ]
    links = [
        {"source": 0, "target": 1, "value": max(marge_brute, 0)},
        {"source": 1, "target": 2, "value": max(rn, 0)},
    ]
    return SankeyData(year=year, nodes=nodes, links=links)
