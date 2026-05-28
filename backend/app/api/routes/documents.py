import logging
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_superadmin
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.storage.client import get_storage_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


def _serialize_document(doc: Document) -> DocumentResponse:
    return DocumentResponse.model_validate({
        "id": doc.id,
        "filename": doc.filename,
        "original_name": doc.original_name,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "status": doc.status,
        "error_message": doc.error_message,
        "doc_type": doc.doc_type,
        "source": doc.source,
        "retrieval_summary": doc.retrieval_summary,
        "ingested_by": doc.ingested_by,
        "parent_document_id": doc.parent_document_id,
        "page_start": doc.page_start,
        "page_end": doc.page_end,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "metadata": doc.metadata_rel,
    })


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    doc_status: Optional[str] = Query(None, alias="status"),
    doc_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    parent_id: Optional[uuid.UUID] = Query(
        None,
        description="Return children of this parent document (a split regulation/policy).",
    ),
    include_parents: bool = Query(
        False,
        description="Include parent container documents (those that were split into sections). "
                    "Defaults to False — only leaf documents are returned.",
    ),
) -> DocumentListResponse:
    base = select(Document)

    if parent_id is not None:
        # Explicit parent filter: return children of a specific document
        base = base.where(Document.parent_document_id == parent_id)
    elif not include_parents:
        # Default: exclude split-parent documents (those referenced as a parent_document_id)
        parents_subquery = select(Document.parent_document_id).where(
            Document.parent_document_id.isnot(None)
        ).scalar_subquery()
        base = base.where(Document.id.not_in(parents_subquery))

    if doc_status is not None:
        base = base.where(Document.status == doc_status)
    if doc_type is not None:
        base = base.where(Document.doc_type == doc_type)
    if source is not None:
        base = base.where(Document.source == source)

    count_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        base.options(selectinload(Document.metadata_rel))
        .order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    docs = result.scalars().all()

    return DocumentListResponse(
        items=[_serialize_document(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentResponse:
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.metadata_rel))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return _serialize_document(doc)


@router.get("/{document_id}/url")
async def get_document_url(
    document_id: uuid.UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage = get_storage_client()
    url = await storage.get_url(doc.file_path)
    return {"url": url, "expires_in": 3600}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    _: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.delete(doc)
    await db.commit()
    logger.info("Document deleted", extra={"document_id": str(document_id)})
