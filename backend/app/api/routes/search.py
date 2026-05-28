import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.retrieval.hybrid import hybrid_search
from app.schemas.search import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SearchResponse:
    """
    Hybrid semantic + BM25 search over the USDA/APHIS corpus.
    Returns top-K documents ranked by combined vector similarity,
    full-text match, and metadata boost — with score breakdown per result.
    """
    logger.info(
        "search request",
        extra={"query": request.query, "top_k": request.top_k, "filters": request.model_dump(exclude={"query", "top_k"})},
    )
    return await hybrid_search(db, request)
