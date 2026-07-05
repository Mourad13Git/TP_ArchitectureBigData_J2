from pydantic import BaseModel


class SearchResult(BaseModel):
    enterprise_number: str
    name: str
    status: str | None = None
    has_gold: bool = False
    latest_ca: float | None = None
    years_count: int = 0


class SankeyNode(BaseModel):
    label: str
    value: float


class SankeyData(BaseModel):
    year: int
    nodes: list[SankeyNode]
    links: list[dict]


class EnterpriseDetail(BaseModel):
    enterprise_number: str
    silver: dict
    gold: dict | None = None
    dirigeants: list[dict] = []
    sankey: SankeyData | None = None
    ejustice_publications: list[dict] = []
    ejustice_liste_url: str | None = None
    contacts: list[dict] = []
