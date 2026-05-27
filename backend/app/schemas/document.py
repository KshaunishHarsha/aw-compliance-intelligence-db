import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DocumentMetadataResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    issuer: Optional[str] = None
    jurisdiction: Optional[str] = None
    facility_name: Optional[str] = None
    species: Optional[List[str]] = None
    inspection_date: Optional[date] = None
    inspector_name: Optional[str] = None
    reference_number: Optional[str] = None
    categories: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_name: str
    file_path: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    doc_type: Optional[str] = None
    source: Optional[str] = None
    retrieval_summary: Optional[str] = None
    ingested_by: Optional[uuid.UUID] = None
    parent_document_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[DocumentMetadataResponse] = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class ChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    chunk_type: str
    page_number: Optional[int] = None
    raw_text: str
    retrieval_summary: Optional[str] = None
    token_count: Optional[int] = None

    model_config = {"from_attributes": True}
