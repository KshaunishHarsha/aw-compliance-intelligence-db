from abc import ABC, abstractmethod

class StorageClient(ABC):
    @abstractmethod
    async def upload(self, file_path: str, content: bytes, content_type: str) -> str:
        """Upload file, return storage path."""

    @abstractmethod
    async def download(self, file_path: str) -> bytes:
        """Download file by storage path."""

    @abstractmethod
    async def get_url(self, file_path: str) -> str:
        """Get a readable URL or presigned URL for the file."""

class LocalStorageClient(StorageClient):
    """For local development — stores files in ./uploads/"""
    
    async def upload(self, file_path: str, content: bytes, content_type: str) -> str:
        raise NotImplementedError
        
    async def download(self, file_path: str) -> bytes:
        raise NotImplementedError
        
    async def get_url(self, file_path: str) -> str:
        raise NotImplementedError

def get_storage_client() -> StorageClient:
    """Returns the right client based on STORAGE_PROVIDER setting."""
    return LocalStorageClient()
