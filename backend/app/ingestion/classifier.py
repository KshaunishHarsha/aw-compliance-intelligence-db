import logging

from app.config import get_settings
from app.llm import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

_VALID_DOC_TYPES = {"inspection_report", "regulation", "policy", "enforcement_action"}

# Grounded on actual corpus document structure:
# - Inspection reports: "Inspection Report" header, certificate number (e.g. 93-C-0119),
#   CFR citation violations (e.g. "2.126(b) REPEAT"), "Prepared By" inspector line,
#   "Species Inspected" table.
# - Enforcement actions: "BEFORE THE SECRETARY OF AGRICULTURE", "AWA Docket No.",
#   "CONSENT DECISION AND ORDER", respondent name, civil penalty amount.
_PROMPT = """\
Classify this USDA/APHIS animal welfare document into exactly one type.

Types:
- inspection_report  — USDA APHIS Inspection Report for a licensed facility.
                       Signals: "Inspection Report" header, certificate number (e.g. 93-C-0119),
                       CFR violation citations (e.g. 2.126(b)), "Prepared By" inspector line,
                       "Species Inspected" table.
- enforcement_action — Consent Decision, Stipulation, or enforcement order.
                       Signals: "BEFORE THE SECRETARY OF AGRICULTURE", "AWA Docket No.",
                       "CONSENT DECISION AND ORDER", civil penalty amount.
- regulation         — Legal regulatory text: Animal Welfare Act statutes or 9 CFR Title 9.
- policy             — APHIS operational policy, inspection guide, or procedure manual.

Pre-classified hint (treat as strong prior, only override if clearly wrong): {hint}

Document text (first 1500 characters):
{text}

Return only the document type string, nothing else.\
"""


def classify(text: str, filename: str, hint: str) -> str:
    """Classify doc_type. Returns hint unchanged on LLM failure."""
    client = get_llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_mini_model,
            messages=[{"role": "user", "content": _PROMPT.format(hint=hint, text=text[:1500])}],
            max_tokens=20,
            temperature=0,
        )
        result = resp.choices[0].message.content.strip().lower()
        if result in _VALID_DOC_TYPES:
            return result
        logger.warning("Classifier returned unknown type %r, keeping hint %r", result, hint)
        return hint
    except Exception as exc:
        logger.error("classify failed: %s", exc)
        return hint
