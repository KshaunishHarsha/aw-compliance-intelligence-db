from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models so Alembic can discover them
from app.models.document import Document, DocumentMetadata, Chunk, Embedding
