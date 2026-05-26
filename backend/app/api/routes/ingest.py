import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_superadmin
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.storage.client import get_storage_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

_VALID_DOC_TYPES = {"inspection_report", "regulation", "policy", "enforcement_action"}
_VALID_SOURCES = {"USDA_APHIS", "CFR_Title9", "APHIS_Enforcement", "APHIS_Policy"}


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_queue(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile,
    doc_type: str = Form(...),
    source: str = Form(...),
) -> DocumentResponse:
    if doc_type not in _VALID_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"doc_type must be one of {sorted(_VALID_DOC_TYPES)}",
        )
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source must be one of {sorted(_VALID_SOURCES)}",
        )

    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    file_id = uuid.uuid4()
    storage_path = f"{doc_type}/{file_id}/{file.filename}"

    storage = get_storage_client()
    await storage.upload(storage_path, content, mime_type)

    doc = Document(
        filename=f"{file_id}_{file.filename}",
        original_name=file.filename or "unknown",
        file_path=storage_path,
        file_size=len(content),
        mime_type=mime_type,
        status="pending",
        doc_type=doc_type,
        source=source,
        ingested_by=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(
        "Document uploaded, pipeline pending",
        extra={"document_id": str(doc.id), "doc_type": doc_type, "source": source},
    )

    # Phase 2: queue Celery ingestion chain here
    # from app.tasks.ingestion import run_ingestion_pipeline
    # run_ingestion_pipeline.delay(str(doc.id))

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
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "metadata": None,
    })
