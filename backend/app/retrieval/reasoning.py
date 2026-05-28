import asyncio
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.config import get_settings
from app.schemas.search import SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()

_PROMPT = """\
You are helping an animal welfare investigator search USDA APHIS documents.

The user searched for: "{query}"

This is one of the matching documents:
- Document type: {doc_type}
- Facility: {facility_name}
- Jurisdiction: {jurisdiction}
- Species involved: {species}
- Violation categories: {categories}
- Summary: {summary}

In 1-2 short sentences, explain *why* this document matches the user's search. Be specific — cite the species, violation type, CFR section, or facility detail that connects to the query. Do not include preamble like "This document matches because…" or "This result is relevant…" — state the connection directly.\
"""


def _get_async_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


async def _generate_one(client: AsyncOpenAI, query: str, result: SearchResult) -> Optional[str]:
    meta = result.metadata
    prompt = _PROMPT.format(
        query=query,
        doc_type=result.doc_type or "unknown",
        facility_name=(meta.facility_name if meta and meta.facility_name else "—"),
        jurisdiction=(meta.jurisdiction if meta and meta.jurisdiction else "—"),
        species=(", ".join(meta.species) if meta and meta.species else "—"),
        categories=(", ".join(meta.categories) if meta and meta.categories else "—"),
        summary=result.retrieval_summary or "(no summary available)",
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.llm_mini_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("reasoning generation failed for %s: %s", result.id, exc)
        return None


async def annotate_with_reasoning(query: str, results: list[SearchResult], top_n: int = 5) -> None:
    """
    Attach match_reason to the top N results in-place.
    Parallelized via asyncio.gather — adds ~1-2s total to a search.
    """
    targets = results[:top_n]
    if not targets:
        return

    client = _get_async_client()
    reasons = await asyncio.gather(*[_generate_one(client, query, r) for r in targets])

    for result, reason in zip(targets, reasons):
        result.match_reason = reason
