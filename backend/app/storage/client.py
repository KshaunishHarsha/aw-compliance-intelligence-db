import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


class StorageClient(ABC):
    @abstractmethod
    async def upload(self, file_path: str, content: bytes, content_type: str) -> str:
        """Upload file content to storage. Returns the storage path."""

    @abstractmethod
    async def download(self, file_path: str) -> bytes:
        """Download file by storage path. Returns raw bytes."""

    @abstractmethod
    async def get_url(self, file_path: str) -> str:
        """Return a signed/accessible URL for the file. Valid for 1 hour."""


class LocalStorageClient(StorageClient):
    """
    Filesystem-based storage for local development.
    Files are stored in ./uploads/ relative to the working directory.
    """

    def __init__(self):
        self.base_dir = Path("uploads")
        self.base_dir.mkdir(exist_ok=True)

    async def upload(self, file_path: str, content: bytes, content_type: str) -> str:
        dest = self.base_dir / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        logger.info("LocalStorage upload", extra={"path": file_path})
        return file_path

    async def download(self, file_path: str) -> bytes:
        dest = self.base_dir / file_path
        return dest.read_bytes()

    async def get_url(self, file_path: str) -> str:
        # In local dev, return a relative path — the API will serve it directly
        return f"/uploads/{file_path}"


class SupabaseStorageClient(StorageClient):
    """
    Supabase Storage client.
    Uses the service role key for server-side access (bypasses RLS).
    Files are uploaded to the configured bucket as private objects.
    Signed URLs are valid for 1 hour.
    """

    def __init__(self):
        from supabase import create_client, Client
        settings = get_settings()
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key,
        )
        self.bucket = settings.supabase_bucket
        logger.info(
            "SupabaseStorageClient initialised",
            extra={"bucket": self.bucket},
        )

    async def upload(self, file_path: str, content: bytes, content_type: str) -> str:
        try:
            self.client.storage.from_(self.bucket).upload(
                path=file_path,
                file=content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            logger.info("Supabase upload ok", extra={"path": file_path})
            return file_path
        except Exception as exc:
            logger.error(
                "Supabase upload failed",
                extra={"path": file_path, "error": str(exc)},
            )
            raise

    async def download(self, file_path: str) -> bytes:
        try:
            data = self.client.storage.from_(self.bucket).download(file_path)
            return data
        except Exception as exc:
            logger.error(
                "Supabase download failed",
                extra={"path": file_path, "error": str(exc)},
            )
            raise

    async def get_url(self, file_path: str) -> str:
        try:
            response = self.client.storage.from_(self.bucket).create_signed_url(
                path=file_path,
                expires_in=3600,
            )
            return response["signedURL"]
        except Exception as exc:
            logger.error(
                "Supabase signed URL failed",
                extra={"path": file_path, "error": str(exc)},
            )
            raise


def get_storage_client() -> StorageClient:
    """
    Returns the correct storage client based on STORAGE_PROVIDER setting.
    supabase → SupabaseStorageClient
    local / anything else → LocalStorageClient (development fallback)
    """
    settings = get_settings()
    provider = settings.storage_provider.lower()

    if provider == "supabase":
        return SupabaseStorageClient()

    logger.warning(
        "Using LocalStorageClient — files stored on disk, not suitable for production",
        extra={"storage_provider": provider},
    )
    return LocalStorageClient()
