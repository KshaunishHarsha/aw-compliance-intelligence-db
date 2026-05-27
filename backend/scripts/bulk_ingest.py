#!/usr/bin/env python3
"""
Bulk ingest script — reads from the corpus/ directory, uploads files to Supabase
Storage, creates document records, and queues the ingestion pipeline for each.

Run inside the api container (corpus is mounted at /app/corpus):
    docker compose exec api python scripts/bulk_ingest.py [options]

Options:
    --corpus-dir PATH     Path to corpus directory (default: /app/corpus)
    --doc-type TYPE       Only ingest one doc type
    --limit N             Stop after N files (useful for testing a subset)
    --dry-run             Show what would be ingested without making any changes
    --skip-upload         Skip Supabase upload; use local path as file_path (dev only)
"""

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# Make sure app/ is importable when running from /app inside the container
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
import app.models.user  # noqa: F401 — required for SQLAlchemy FK resolution
from app.models.document import Document
from app.storage.client import get_storage_client
from app.tasks.ingestion import run_ingestion_pipeline

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger("bulk_ingest")

# Maps corpus subdirectory name → (doc_type, source)
_DIRECTORY_MAP: dict[str, tuple[str, str]] = {
    "inspection_reports": ("inspection_report", "USDA_APHIS"),
    "enforcement_actions": ("enforcement_action", "APHIS_Enforcement"),
    "regulations":         ("regulation",         "CFR_Title9"),
    "policies":            ("policy",             "APHIS_Policy"),
}

_MIME_MAP: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt":  "text/plain",
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bulk ingest corpus documents")
    p.add_argument("--corpus-dir", default="/app/corpus")
    p.add_argument("--doc-type", choices=[v[0] for v in _DIRECTORY_MAP.values()])
    p.add_argument("--limit", type=int, help="Max files to process")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-upload", action="store_true",
                   help="Use local file path instead of uploading (dev only)")
    return p.parse_args()


def _get_session():
    settings = get_settings()
    engine = sa.create_engine(settings.sync_database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


def _already_ingested(session, original_name: str) -> bool:
    return (
        session.query(Document)
        .filter(Document.original_name == original_name)
        .first()
    ) is not None


async def _upload(storage, storage_path: str, file_bytes: bytes, mime_type: str) -> None:
    await storage.upload(storage_path, file_bytes, mime_type)


def _process_file(
    session,
    storage,
    file_path: Path,
    doc_type: str,
    source: str,
    dry_run: bool,
    skip_upload: bool,
) -> str:
    """
    Returns: "queued" | "skipped" | "failed"
    """
    original_name = file_path.name

    if _already_ingested(session, original_name):
        logger.info("SKIP  already ingested: %s", original_name)
        return "skipped"

    mime_type = _MIME_MAP.get(file_path.suffix.lower(), "application/octet-stream")

    if dry_run:
        logger.info("DRY   would ingest: %s  [%s / %s]", original_name, doc_type, source)
        return "queued"

    file_bytes = file_path.read_bytes()
    file_id = uuid.uuid4()

    if skip_upload:
        storage_path = str(file_path)
    else:
        storage_path = f"{doc_type}/{file_id}/{original_name}"
        try:
            asyncio.run(_upload(storage, storage_path, file_bytes, mime_type))
        except Exception as exc:
            logger.error("FAIL  upload failed for %s: %s", original_name, exc)
            return "failed"

    doc = Document(
        filename=f"{file_id}_{original_name}",
        original_name=original_name,
        file_path=storage_path,
        file_size=len(file_bytes),
        mime_type=mime_type,
        status="pending",
        doc_type=doc_type,
        source=source,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    run_ingestion_pipeline(str(doc.id))
    logger.info("OK    queued: %s  document_id=%s", original_name, doc.id)
    return "queued"


def main() -> None:
    args = _parse_args()
    corpus_dir = Path(args.corpus_dir)

    if not corpus_dir.exists():
        logger.error("Corpus directory not found: %s", corpus_dir)
        sys.exit(1)

    session = _get_session()
    storage = get_storage_client()

    total = queued = skipped = failed = 0

    for subdir_name, (doc_type, source) in _DIRECTORY_MAP.items():
        if args.doc_type and doc_type != args.doc_type:
            continue

        subdir = corpus_dir / subdir_name
        if not subdir.exists():
            logger.warning("Subdirectory not found, skipping: %s", subdir)
            continue

        files = sorted(
            f for f in subdir.iterdir()
            if f.is_file() and f.suffix.lower() in _MIME_MAP
        )
        logger.info("--- %s: %d files ---", subdir_name, len(files))

        for file_path in files:
            if args.limit and total >= args.limit:
                break
            total += 1
            try:
                result = _process_file(
                    session, storage, file_path, doc_type, source,
                    dry_run=args.dry_run,
                    skip_upload=args.skip_upload,
                )
                if result == "queued":
                    queued += 1
                elif result == "skipped":
                    skipped += 1
                else:
                    failed += 1
            except Exception as exc:
                logger.error("FAIL  unhandled error for %s: %s", file_path.name, exc)
                failed += 1

        if args.limit and total >= args.limit:
            logger.info("Limit of %d reached, stopping.", args.limit)
            break

    logger.info(
        "Done — total=%d  queued=%d  skipped=%d  failed=%d",
        total, queued, skipped, failed,
    )


if __name__ == "__main__":
    main()
