import asyncio
import logging

from celery import chain
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.document import Document, DocumentMetadata
from celery_worker import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
_Session = sessionmaker(bind=_engine)


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_doc(session: Session, document_id: str) -> Document:
    return session.query(Document).filter(Document.id == document_id).one()


def _fail(session: Session, document_id: str, stage: str, exc: Exception) -> None:
    session.query(Document).filter(Document.id == document_id).update(
        {"status": "failed", "error_message": f"{stage}: {exc}"},
        synchronize_session=False,
    )
    session.commit()
    logger.error("%s failed", stage, extra={"document_id": document_id, "error": str(exc)})


# ── public entry point ────────────────────────────────────────────────────────

def run_ingestion_pipeline(document_id: str) -> None:
    """Queue the full ingestion pipeline chain for a document."""
    pipeline = chain(
        task_ocr_extract.si(document_id),
        task_clean.si(document_id),
        task_classify.si(document_id),
        task_section_split.si(document_id),
    )
    pipeline.apply_async()
    logger.info("Ingestion pipeline queued", extra={"document_id": document_id})


# ── pipeline tasks ────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.ocr_extract", max_retries=2, default_retry_delay=15)
def task_ocr_extract(self, document_id: str) -> None:
    logger.info("ocr_extract start", extra={"document_id": document_id})
    with _Session() as session:
        try:
            doc = _get_doc(session, document_id)
            session.query(Document).filter(Document.id == document_id).update(
                {"status": "processing"}, synchronize_session=False
            )
            session.commit()

            from app.storage.client import get_storage_client
            storage = get_storage_client()
            file_bytes = asyncio.run(storage.download(doc.file_path))

            from app.ingestion.ocr import extract_text
            raw_text = extract_text(file_bytes, doc.mime_type or "application/pdf")

            session.query(Document).filter(Document.id == document_id).update(
                {"raw_text": raw_text}, synchronize_session=False
            )
            session.commit()
            logger.info(
                "ocr_extract done",
                extra={"document_id": document_id, "chars": len(raw_text)},
            )
        except Exception as exc:
            _fail(session, document_id, "ocr_extract", exc)
            raise self.retry(exc=exc)


@celery_app.task(bind=True, name="tasks.clean", max_retries=2, default_retry_delay=15)
def task_clean(self, document_id: str) -> None:
    logger.info("clean start", extra={"document_id": document_id})
    with _Session() as session:
        try:
            doc = _get_doc(session, document_id)
            if not doc.raw_text:
                raise ValueError("raw_text is empty before clean stage")

            from app.ingestion.cleaner import clean_text
            cleaned = clean_text(doc.raw_text)

            session.query(Document).filter(Document.id == document_id).update(
                {"raw_text": cleaned}, synchronize_session=False
            )
            session.commit()
            logger.info("clean done", extra={"document_id": document_id})
        except Exception as exc:
            _fail(session, document_id, "clean", exc)
            raise self.retry(exc=exc)


@celery_app.task(bind=True, name="tasks.classify", max_retries=2, default_retry_delay=15)
def task_classify(self, document_id: str) -> None:
    logger.info("classify start", extra={"document_id": document_id})
    with _Session() as session:
        try:
            doc = _get_doc(session, document_id)

            from app.ingestion.classifier import classify
            result = classify(
                text=doc.raw_text or "",
                filename=doc.original_name,
                hint=doc.doc_type or "inspection_report",
            )

            if result != doc.doc_type:
                logger.info(
                    "classify corrected doc_type",
                    extra={"document_id": document_id, "old": doc.doc_type, "new": result},
                )
            session.query(Document).filter(Document.id == document_id).update(
                {"doc_type": result}, synchronize_session=False
            )
            session.commit()
            logger.info(
                "classify done",
                extra={"document_id": document_id, "doc_type": result},
            )
        except Exception as exc:
            _fail(session, document_id, "classify", exc)
            raise self.retry(exc=exc)


@celery_app.task(bind=True, name="tasks.section_split", max_retries=2, default_retry_delay=15)
def task_section_split(self, document_id: str) -> None:
    """
    Route after classify:
    - inspection_report / enforcement_action → enrich directly (no split needed).
    - regulation / policy → split into sections, create child Document rows,
      queue classify→enrich for each child, mark parent complete.
    If the splitter finds only one section, falls through to enrich as a whole doc.
    """
    logger.info("section_split start", extra={"document_id": document_id})
    with _Session() as session:
        try:
            doc = _get_doc(session, document_id)
            doc_type = doc.doc_type or ""

            if doc_type not in ("regulation", "policy"):
                # Not a large doc type — enrich the whole document
                task_enrich.apply_async(args=[document_id])
                logger.info(
                    "section_split: skipped (not regulation/policy), routing to enrich",
                    extra={"document_id": document_id, "doc_type": doc_type},
                )
                return

            from app.storage.client import get_storage_client
            from app.ingestion.section_splitter import split_into_sections

            try:
                storage = get_storage_client()
                file_bytes = asyncio.run(storage.download(doc.file_path))
            except Exception as dl_exc:
                logger.warning(
                    "section_split: file download failed, splitting text-only: %s", dl_exc,
                    extra={"document_id": document_id},
                )
                file_bytes = None

            sections = split_into_sections(doc.raw_text or "", doc_type, file_bytes=file_bytes)

            if len(sections) <= 1:
                # Document didn't split meaningfully — enrich as a whole
                task_enrich.apply_async(args=[document_id])
                logger.info(
                    "section_split: single section, routing to enrich",
                    extra={"document_id": document_id, "sections": len(sections)},
                )
                return

            logger.info(
                "section_split: splitting into %d sections",
                len(sections),
                extra={"document_id": document_id},
            )

            for section in sections:
                child = Document(
                    filename=f"{doc.id}_s{section.section_index}_{doc.filename}",
                    original_name=f"[{section.title}] {doc.original_name}",
                    file_path=doc.file_path,
                    file_size=len(section.text.encode("utf-8", errors="replace")),
                    mime_type=doc.mime_type,
                    status="pending",
                    doc_type=doc.doc_type,
                    source=doc.source,
                    raw_text=section.text,
                    parent_document_id=doc.id,
                )
                session.add(child)
                session.flush()  # populate child.id before queuing

                chain(
                    task_classify.si(str(child.id)),
                    task_enrich.si(str(child.id)),
                ).apply_async()

                logger.info(
                    "section_split: child queued",
                    extra={
                        "parent_id": document_id,
                        "child_id": str(child.id),
                        "section": section.title,
                    },
                )

            # Mark parent as complete — it is a storage/provenance container only
            session.query(Document).filter(Document.id == document_id).update(
                {"status": "complete"}, synchronize_session=False
            )
            session.commit()
            logger.info(
                "section_split done",
                extra={"document_id": document_id, "children": len(sections)},
            )
        except Exception as exc:
            _fail(session, document_id, "section_split", exc)
            raise self.retry(exc=exc)


@celery_app.task(bind=True, name="tasks.enrich", max_retries=2, default_retry_delay=30)
def task_enrich(self, document_id: str) -> None:
    """Metadata extraction, categorization, and retrieval summary — all in one task."""
    logger.info("enrich start", extra={"document_id": document_id})
    with _Session() as session:
        try:
            doc = _get_doc(session, document_id)
            text = doc.raw_text or ""
            doc_type = doc.doc_type or "inspection_report"

            from app.ingestion.metadata_extractor import extract_metadata
            from app.ingestion.categorizer import categorize
            from app.ingestion.summarizer import generate_retrieval_summary

            metadata = extract_metadata(text, doc_type)
            categories = categorize(text)
            retrieval_summary = generate_retrieval_summary(text, doc_type)

            # Upsert document_metadata row
            existing = (
                session.query(DocumentMetadata)
                .filter(DocumentMetadata.document_id == document_id)
                .first()
            )
            if existing:
                for k, v in metadata.items():
                    setattr(existing, k, v)
                if categories:
                    existing.categories = categories
            else:
                dm = DocumentMetadata(
                    document_id=document_id,
                    **metadata,
                    categories=categories or None,
                )
                session.add(dm)

            session.query(Document).filter(Document.id == document_id).update(
                {"retrieval_summary": retrieval_summary, "status": "complete"},
                synchronize_session=False,
            )
            session.commit()
            logger.info(
                "enrich done",
                extra={"document_id": document_id, "categories": categories},
            )
        except Exception as exc:
            _fail(session, document_id, "enrich", exc)
            raise self.retry(exc=exc)


# ── kept for smoke-testing the worker ────────────────────────────────────────

@celery_app.task(bind=True, name="tasks.ping")
def ping(self) -> dict:
    logger.info("ping task received", extra={"task_id": self.request.id})
    return {"status": "pong"}
