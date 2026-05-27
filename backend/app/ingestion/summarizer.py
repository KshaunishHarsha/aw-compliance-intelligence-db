import logging

from app.config import get_settings
from app.llm import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

# The retrieval summary is NOT human-readable. It is a keyword-dense artifact that:
#   - weights 'A' in the FTS trigger (higher than raw_text 'B')
#   - bridges informal source language to normalized AWA/APHIS regulatory terminology
#   - improves both BM25 recall and vector similarity by reducing vocabulary mismatch
#
# Grounded example from corpus:
#   raw: "A responsible adult was not available to accompany APHIS Officials during
#         the inspection process at 1:35 PM on 02/20/2015"
#   summary: "USDA APHIS inspection access refusal 9 CFR §2.126(b) recordkeeping
#             noncompliance California dealer certificate 93-C-0119 attempted inspection"
_PROMPT = """\
Generate a retrieval summary for this USDA APHIS animal welfare compliance document.

PURPOSE: NOT a human-readable summary. A keyword-dense, normalized-terminology artifact
to improve both BM25 full-text search and semantic vector retrieval. Bridge informal or
inconsistent source language to standard AWA/APHIS regulatory terminology.

RULES:
- Use standard regulatory terminology: AWA, 9 CFR Part 2/Part 3, APHIS, Animal Care
- Include: species, violation types, CFR section numbers, facility type, certificate or docket numbers
- 150-250 words of keywords and short phrases — NOT prose sentences
- Do not include legal conclusions, opinions, or case outcomes
- Normalize informal language (e.g. "animals without water" → "inadequate potable water access 9 CFR §3.9")

EXAMPLE for inspection_report:
"USDA APHIS inspection report AWA Animal Welfare Act noncompliance 9 CFR Part 3
attending veterinarian veterinary care §2.40 inadequate medical treatment
dogs canines housing facility sanitation unsanitary conditions §3.11
water access potable water §3.9 recordkeeping §2.75 repeated violation
California dealer license certificate 93-C-0119 REPEAT noncompliance Animal Care"

Document type: {doc_type}
Document text (first 4000 characters):
{text}

Return only the retrieval summary text, no preamble.\
"""


def generate_retrieval_summary(text: str, doc_type: str) -> str:
    client = get_llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_mini_model,
            messages=[{"role": "user", "content": _PROMPT.format(doc_type=doc_type, text=text[:4000])}],
            max_tokens=400,
            temperature=0.1,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("summarizer failed: %s", exc)
        return ""
