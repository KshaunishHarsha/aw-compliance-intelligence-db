import json
import logging

from app.config import get_settings
from app.llm import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

_VALID_CATEGORIES = frozenset({
    "overcrowding", "veterinary_care", "transport_conditions", "sanitation",
    "water_access", "euthanasia", "housing", "feeding", "handling", "recordkeeping",
})

# CFR citation anchors grounded on inspection report format.
# Reports cite violations as "§2.126(b) REPEAT" or "3.11(a)" in the violation header block.
_PROMPT = """\
Classify this USDA APHIS animal welfare document into applicable violation/issue categories.

Valid categories and their AWA/CFR regulatory context:
- overcrowding        — space requirement violations (9 CFR §3.x housing space per animal)
- veterinary_care     — inadequate veterinary care, attending vet program failures (9 CFR §2.40)
- transport_conditions— violations during transport, vehicle/carrier standards (9 CFR §3.x transport)
- sanitation          — unsanitary conditions, cleaning/sanitizing failures (9 CFR §3.11, §3.31, §3.131)
- water_access        — inadequate potable water supply or access (9 CFR §3.9, §3.29, §3.129)
- euthanasia          — improper euthanasia methods or equipment (9 CFR §2.x)
- housing             — inadequate housing facilities, shelter, temperature, lighting (9 CFR §3.x housing)
- feeding             — inadequate food supply, contamination, feeding failures (9 CFR §3.9, §3.29)
- handling            — improper animal handling, public contact violations (9 CFR §2.131)
- recordkeeping       — recordkeeping failures, access/inspection refusal (9 CFR §2.75, §2.126)

Return a JSON array of applicable category strings. Return [] if none clearly apply.

Document text (first 3000 characters):
{text}

Return only the JSON array, e.g. ["recordkeeping"] or ["veterinary_care", "housing"] or []\
"""


def categorize(text: str) -> list[str]:
    client = get_llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_mini_model,
            messages=[{"role": "user", "content": _PROMPT.format(text=text[:3000])}],
            max_tokens=100,
            temperature=0,
        )
        parsed = json.loads(resp.choices[0].message.content.strip())
        if isinstance(parsed, list):
            return [c for c in parsed if c in _VALID_CATEGORIES]
        return []
    except Exception as exc:
        logger.error("categorizer failed: %s", exc)
        return []
