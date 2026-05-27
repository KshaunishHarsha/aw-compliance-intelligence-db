import logging
from typing import Optional

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_embedding_client() -> OpenAI:
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


def build_embedding_input(
    retrieval_summary: Optional[str],
    facility_name: Optional[str],
    jurisdiction: Optional[str],
    species: Optional[list[str]],
    categories: Optional[list[str]],
    doc_type: Optional[str],
) -> str:
    parts = [retrieval_summary or ""]
    if facility_name:
        parts.append(facility_name)
    if jurisdiction:
        parts.append(jurisdiction)
    if species:
        parts.append(" ".join(species))
    if categories:
        parts.append(" ".join(categories))
    if doc_type:
        parts.append(doc_type)
    return " ".join(p for p in parts if p).strip()


def embed(text: str) -> list[float]:
    client = get_embedding_client()
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=text[:8000],  # text-embedding-3-small max input
    )
    return resp.data[0].embedding
