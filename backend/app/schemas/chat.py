import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    cit_id: int                              # the [CIT-N] index
    document_id: uuid.UUID
    section: Optional[str] = None            # human label (e.g. "Findings", "Subpart A")
    snippet: str                             # the cited passage text


class ConversationCreate(BaseModel):
    scope_type: Literal["document", "result_set"]
    scope_document_id: Optional[uuid.UUID] = None
    scope_query: Optional[str] = None
    scope_filters: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    citations: Optional[List[Citation]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    scope_type: str
    scope_document_id: Optional[uuid.UUID] = None
    scope_query: Optional[str] = None
    scope_filters: Optional[Dict[str, Any]] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class ConversationListItem(BaseModel):
    """Lightweight conversation summary for the /chat list page."""
    id: uuid.UUID
    scope_type: str
    scope_document_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    # Scope context — joined from documents + document_metadata
    scope_doc_type: Optional[str] = None
    scope_doc_original_name: Optional[str] = None
    scope_doc_facility_name: Optional[str] = None
    scope_doc_jurisdiction: Optional[str] = None


class ConversationListResponse(BaseModel):
    items: List[ConversationListItem]
    total: int
