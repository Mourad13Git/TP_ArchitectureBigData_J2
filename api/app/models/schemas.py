from pydantic import BaseModel


class SearchResult(BaseModel):
    enterprise_number: str
    name: str
    status: str | None = None


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
