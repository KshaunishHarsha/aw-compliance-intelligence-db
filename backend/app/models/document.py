from typing import List, Optional, Any
import uuid
from datetime import datetime

from sqlalchemy import String, Text, BigInteger, Integer, text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    doc_type: Mapped[Optional[str]] = mapped_column(Text)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    retrieval_summary: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))

    metadata_rel: Mapped["DocumentMetadata"] = relationship(back_populates="document", cascade="all, delete-orphan", uselist=False)
    chunks: Mapped[List["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    issuer: Mapped[Optional[str]] = mapped_column(Text)
    jurisdiction: Mapped[Optional[str]] = mapped_column(Text)
    facility_name: Mapped[Optional[str]] = mapped_column(Text)
    species: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    inspection_date: Mapped[Optional[datetime]] = mapped_column()
    inspector_name: Mapped[Optional[str]] = mapped_column(Text)
    reference_number: Mapped[Optional[str]] = mapped_column(Text)
    categories: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    extra: Mapped[Optional[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    document: Mapped["Document"] = relationship(back_populates="metadata_rel")

    def __repr__(self) -> str:
        return f"<DocumentMetadata(id={self.id}, document_id={self.document_id})>"

class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_summary: Mapped[Optional[str]] = mapped_column(Text)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    # fts_vector should not be populated by the application, it's managed by a trigger
    fts_vector: Mapped[Optional[Any]] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    document: Mapped["Document"] = relationship(back_populates="chunks")
    embeddings: Mapped[List["Embedding"]] = relationship(back_populates="chunk", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, chunk_index={self.chunk_index}, chunk_type={self.chunk_type})>"

class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False, server_default="text-embedding-3-small")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    chunk: Mapped["Chunk"] = relationship(back_populates="embeddings")

    def __repr__(self) -> str:
        return f"<Embedding(id={self.id}, chunk_id={self.chunk_id}, model={self.model})>"
