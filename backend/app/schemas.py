from pydantic import BaseModel
from typing import List, Optional


class DocumentResult(BaseModel):
    id: int
    title: str
    url: str
    snippet: str
    category: Optional[str] = ""
    document_type: Optional[str] = ""
    published_date: Optional[str] = ""
    rank: float = 0.0

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    query: str
    total: int
    page: int
    limit: int
    has_more: bool
    results: List[DocumentResult]
    search_time_ms: float


class StatsResponse(BaseModel):
    total_documents: int
    categories: List[dict]
    last_crawled: Optional[str] = None


class CrawlStatusResponse(BaseModel):
    status: str
    message: str
