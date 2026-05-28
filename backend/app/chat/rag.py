"""
Grounded RAG chat pipeline.

Constraints (non-negotiable, enforced in three layers):
  1. Refuses to draw legal conclusions or call anything a confirmed violation.
  2. Refuses claims not supported by retrieved chunks.
  3. Frames findings as potential observations, not facts.

Defense in depth:
  - Strong system prompt encoding the three constraints in absolute terms.
  - Retrieval bounding: passages are limited to the document scope; the model
    only sees what it is allowed to cite.
  - Response validation: citation markers are parsed and resolved against the
    actual provided passages; verdict language is detected and logged.

V1.0 supports document-scope chat only. Result-set scope is deferred.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.chat import Message
from app.models.document import Document

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Passage prep ──────────────────────────────────────────────────────────

_MIN_PASSAGE_CHARS = 200
_MAX_PASSAGE_CHARS = 2500
_MAX_PASSAGES_PER_DOC = 30


@dataclass
class Passage:
    cit_id: int
    document_id: str
    section: str        # short label, e.g. "Findings", "§3.131", or just "Passage 4"
    text: str


def _split_into_passages(raw_text: str, document_id: str) -> List[Passage]:
    """
    Split raw_text into ~2500-char passages, preferring paragraph boundaries.
    Each passage gets a CIT-N id starting from 1.
    """
    if not raw_text or not raw_text.strip():
        return []

    # Normalize whitespace and split on blank lines first
    blocks = re.split(r"\n{2,}", raw_text.strip())

    passages: List[Passage] = []
    current = ""
    section_label: Optional[str] = None

    def _flush(label: Optional[str], text: str) -> None:
        text = text.strip()
        if len(text) < _MIN_PASSAGE_CHARS:
            return
        passages.append(
            Passage(
                cit_id=len(passages) + 1,
                document_id=document_id,
                section=label or f"Passage {len(passages) + 1}",
                text=text[:_MAX_PASSAGE_CHARS],
            )
        )

    # Heuristic: detect section-y looking lines (short ALL-CAPS or starting with §)
    section_re = re.compile(r"^(?:§\s*[\d\.\(\)a-zA-Z]+|[A-Z][A-Z \d\-\—]{4,60})\s*$")

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Try to pull a section header off the first line of a block
        first_line = block.split("\n", 1)[0]
        if section_re.match(first_line) and len(first_line) < 80:
            if current:
                _flush(section_label, current)
                current = ""
            section_label = first_line.strip()
            rest = block[len(first_line):].strip()
            if rest:
                current = rest
            continue

        if len(current) + len(block) + 2 > _MAX_PASSAGE_CHARS and current:
            _flush(section_label, current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block

        if len(passages) >= _MAX_PASSAGES_PER_DOC:
            break

    if current and len(passages) < _MAX_PASSAGES_PER_DOC:
        _flush(section_label, current)

    return passages


# ── Prompt construction ───────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an assistant helping an animal welfare investigator review USDA APHIS \
compliance documents. You answer ONLY based on the document passages provided \
to you. You do not have outside knowledge of these cases.

CONSTRAINTS (non-negotiable):
1. NO LEGAL CONCLUSIONS. Never declare anything a "violation", "guilty", \
"compliant", "non-compliant", or render any verdict. The investigator decides \
those. Your job is to surface what the document says.
2. CITE EVERYTHING. Every factual statement must include an inline citation \
in the form [CIT-N] referring to one of the passages provided. If a claim has \
no citation, do not state it.
3. NO UNSUPPORTED CLAIMS. If the passages do not contain the answer, say so \
explicitly ("The provided passages do not address this question."). Do NOT \
guess, infer beyond what is written, or use outside knowledge.
4. OBSERVATIONAL LANGUAGE ONLY. Use phrases like "the report notes…", "the \
inspector documented…", "the passage describes…". Never "this is a violation" \
or "the facility failed to…".
5. BE CONCISE. Investigators are scanning for facts. 2-4 short sentences is \
usually the right answer.

If a user question requests legal interpretation, predictions, or \
recommendations, refuse politely and explain that you can only summarize what \
the documents say."""


def _build_passages_block(passages: List[Passage]) -> str:
    lines: List[str] = []
    for p in passages:
        lines.append(f"[CIT-{p.cit_id}] (Section: {p.section})")
        lines.append(p.text)
        lines.append("")
    return "\n".join(lines).strip()


def _build_messages(
    passages: List[Passage],
    history: List[Message],
    user_message: str,
) -> List[dict]:
    """
    Build the LLM message list:
      - system prompt
      - passages as a system-role context block
      - last 8 messages of history (4 turns)
      - current user message
    """
    msgs: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if passages:
        passages_block = _build_passages_block(passages)
        msgs.append({
            "role": "system",
            "content": f"DOCUMENT PASSAGES (cite these as [CIT-N]):\n\n{passages_block}",
        })
    else:
        msgs.append({
            "role": "system",
            "content": "DOCUMENT PASSAGES: (none — the document has no extractable text).",
        })

    # Last 4 turns max (8 messages) for context, oldest first
    recent = list(history)[-8:]
    for m in recent:
        if m.role in ("user", "assistant"):
            msgs.append({"role": m.role, "content": m.content})

    msgs.append({"role": "user", "content": user_message})
    return msgs


# ── Response validation ───────────────────────────────────────────────────

_CIT_RE = re.compile(r"\[CIT-(\d+)\]")

# Verdict words that should not appear in assistant output.
# We log when they do but do not block — over-blocking would hurt UX more
# than the constraint protects against, given the prompt already pushes
# observational framing.
_VERDICT_PATTERNS = [
    r"\bis (?:a |an )?violation\b",
    r"\b(?:was|were|is|are) (?:in )?violation of\b",
    r"\b(?:guilty|innocent) of\b",
    r"\b(?:is|was|are|were) (?:non[\-\s]?compliant|noncompliant)\b",
    r"\bthe facility (?:failed to|violated)\b",
]


def parse_citations(content: str, passages: List[Passage]) -> List[dict]:
    """
    Find [CIT-N] markers, resolve each to its passage, and return a list of
    {cit_id, document_id, section, snippet} dicts (deduped by cit_id).
    """
    by_id = {p.cit_id: p for p in passages}
    seen: set[int] = set()
    out: List[dict] = []
    for match in _CIT_RE.finditer(content):
        cit_id = int(match.group(1))
        if cit_id in seen or cit_id not in by_id:
            continue
        seen.add(cit_id)
        p = by_id[cit_id]
        snippet = p.text[:240].rstrip()
        if len(p.text) > 240:
            snippet += "…"
        out.append({
            "cit_id": cit_id,
            "document_id": p.document_id,
            "section": p.section,
            "snippet": snippet,
        })
    return out


def detect_verdict_language(content: str) -> List[str]:
    """Return any verdict phrases found (lowercased)."""
    text = content.lower()
    hits: List[str] = []
    for pat in _VERDICT_PATTERNS:
        m = re.search(pat, text)
        if m:
            hits.append(m.group(0))
    return hits


# ── Pipeline entry point ──────────────────────────────────────────────────

async def load_passages_for_document(
    db: AsyncSession, document_id: str
) -> tuple[List[Passage], Optional[Document]]:
    """Load a document and split its raw_text into passages."""
    from sqlalchemy import select
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        return [], None
    passages = _split_into_passages(doc.raw_text or "", str(doc.id))
    return passages, doc


def get_async_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )


async def stream_response(
    user_message: str,
    passages: List[Passage],
    history: List[Message],
) -> AsyncIterator[str]:
    """Stream the assistant response token-by-token from the LLM."""
    client = get_async_llm_client()
    msgs = _build_messages(passages, history, user_message)

    stream = await client.chat.completions.create(
        model=settings.llm_chat_model,
        messages=msgs,
        temperature=0.1,
        max_tokens=600,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
