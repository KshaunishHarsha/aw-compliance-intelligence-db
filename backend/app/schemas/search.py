from datetime import date
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    # Either query or at least one filter must be present.
    # An empty/missing query triggers filter-only mode (ordered by inspection_date).
    query: Optional[str] = Field(None, max_length=500)
    top_k: int = Field(20, ge=1, le=100)

    # Document-level filters
    doc_type: Optional[str] = None          # inspection_report | regulation | policy | enforcement_action
    source: Optional[str] = None            # USDA_APHIS | CFR_Title9 | APHIS_Enforcement

    # Violation / issue filters (OR logic — match any selected)
    categories: Optional[List[str]] = None

    # Metadata filters
    jurisdiction: Optional[str] = None     # 2-letter state code
    facility_name: Optional[str] = None    # ILIKE partial match
    species: Optional[List[str]] = None    # OR logic
    inspector_name: Optional[str] = None   # ILIKE partial match
    reference_number: Optional[str] = None # exact match

    # Date range (inspection_date or decision_date)
    date_from: Optional[date] = None
    date_to: Optional[date] = None

    # Result options
    include_parents: bool = False

    # Retrieval weight overrides (defaults from CLAUDE.md)
    vector_weight: float = Field(0.6, ge=0.0, le=1.0)
    bm25_weight: float = Field(0.3, ge=0.0, le=1.0)
    metadata_weight: float = Field(0.1, ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    vector_score: float
    bm25_score: float
    metadata_boost: float
    final_score: float


class SearchResultMetadata(BaseModel):
    issuer: Optional[str] = None
    jurisdiction: Optional[str] = None
    facility_name: Optional[str] = None
    species: Optional[List[str]] = None
    inspection_date: Optional[date] = None
    inspector_name: Optional[str] = None
    reference_number: Optional[str] = None
    categories: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    id: uuid.UUID
    original_name: str
    doc_type: Optional[str]
    source: Optional[str]
    retrieval_summary: Optional[str]
    parent_document_id: Optional[uuid.UUID]
    metadata: Optional[SearchResultMetadata]
    scores: ScoreBreakdown
    match_reason: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResult]
