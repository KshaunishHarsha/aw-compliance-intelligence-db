"""
One-off backfill: compute page_start/page_end for child sections of the
three existing parent regulation/policy documents and patch the existing
child Document rows in place (matched by their original_name which embeds
the section title).

Run inside the api container:
    docker compose exec api python scripts/backfill_page_ranges.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models.user  # noqa: F401 — FK resolution
from app.config import get_settings
from app.ingestion.section_splitter import split_into_sections
from app.models.document import Document
from app.storage.client import get_storage_client

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("backfill")

settings = get_settings()
engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def backfill_one(session: Session, parent_id: str) -> None:
    parent = session.query(Document).filter(Document.id == parent_id).one()
    logger.info("Parent: %s (%s)", parent.original_name, parent.id)

    storage = get_storage_client()
    file_bytes = asyncio.run(storage.download(parent.file_path))
    sections = split_into_sections(
        parent.raw_text or "", parent.doc_type or "", file_bytes=file_bytes,
    )
    logger.info("Computed %d sections", len(sections))

    # Map each section to the matching existing child by original_name.
    # task_section_split builds child.original_name as f"[{section.title}] {parent.original_name}".
    children = (
        session.query(Document)
        .filter(Document.parent_document_id == parent.id)
        .all()
    )
    by_name = {c.original_name: c for c in children}

    updated = 0
    missing = 0
    for s in sections:
        expected_name = f"[{s.title}] {parent.original_name}"
        child = by_name.get(expected_name)
        if child is None:
            missing += 1
            logger.warning(
                "no child for section %r (expected name %r)",
                s.title, expected_name,
            )
            continue
        old = (child.page_start, child.page_end)
        child.page_start = s.page_start
        child.page_end = s.page_end
        if old != (s.page_start, s.page_end):
            updated += 1
            logger.info(
                "  %-70s pp. %s–%s",
                s.title[:70], s.page_start, s.page_end,
            )
    session.commit()
    logger.info("Updated %d / %d sections (%d unmatched)", updated, len(sections), missing)


def main() -> None:
    with SessionLocal() as session:
        # Find every parent that has child sections
        rows = session.execute(text("""
            SELECT DISTINCT d.id, d.original_name, d.doc_type
            FROM documents d
            JOIN documents c ON c.parent_document_id = d.id
            ORDER BY d.original_name
        """)).fetchall()
        logger.info("Found %d parent docs with children", len(rows))
        for parent_id, name, doc_type in rows:
            logger.info("=== %s (%s) ===", name, doc_type)
            try:
                backfill_one(session, str(parent_id))
            except Exception as exc:
                logger.exception("Failed for %s: %s", parent_id, exc)


if __name__ == "__main__":
    main()
