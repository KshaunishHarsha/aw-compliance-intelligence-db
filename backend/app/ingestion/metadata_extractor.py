import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from app.config import get_settings
from app.llm import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

# Grounded on corpus document structure:
# Inspection reports: facility address contains state (e.g. "Weimar, CA 95736" → "CA"),
#   certificate in header (e.g. "93-C-0119"), inspection date as "20-FEB-2015",
#   inspector in "Prepared By" line, species in "Species Inspected" table.
# Enforcement actions: respondent address contains state (e.g. "Fort Pierce, FL 34945" → "FL"),
#   AWA Docket No. in caption (e.g. "AWA Docket No. 25-J-0069"),
#   AWA license in Findings of Fact (e.g. "58-C-0706"), decision date in signature block.
_PROMPT = """\
Extract structured metadata from this USDA APHIS animal welfare compliance document.

Document type: {doc_type}

Return a JSON object. Use null for any field not found.
{{
  "issuer": "USDA APHIS",
  "jurisdiction": "<two-letter US state abbreviation from facility or respondent address>",
  "facility_name": "<licensed facility name, licensee name, or respondent/entity name>",
  "species": ["<common species names mentioned, e.g. dogs, cats, nonhuman primates, birds, rabbits>"],
  "inspection_date": "<YYYY-MM-DD — inspection date for reports, decision date for enforcement actions; null if absent>",
  "inspector_name": "<full inspector name from Prepared By field, or null>",
  "reference_number": "<AWA certificate number (e.g. 93-C-0119) or AWA Docket No. (e.g. AWA Docket No. 25-J-0069)>"
}}

Document text (first 3000 characters):
{text}

Return only the JSON object.\
"""


def extract_metadata(text: str, doc_type: str) -> dict[str, Any]:
    client = get_llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_mini_model,
            messages=[{"role": "user", "content": _PROMPT.format(doc_type=doc_type, text=text[:3000])}],
            max_tokens=400,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content.strip())
    except Exception as exc:
        logger.error("metadata_extractor failed: %s", exc)
        data = {}

    return _normalize(data)


def _normalize(data: dict) -> dict[str, Any]:
    return {
        "issuer": _str(data.get("issuer")),
        "jurisdiction": _str(data.get("jurisdiction")),
        "facility_name": _str(data.get("facility_name")),
        "species": _strlist(data.get("species")),
        "inspection_date": _date(data.get("inspection_date")),
        "inspector_name": _str(data.get("inspector_name")),
        "reference_number": _str(data.get("reference_number")),
    }


def _str(val: Any) -> Optional[str]:
    if val and str(val).strip() and str(val).strip().lower() not in ("null", "none", "n/a"):
        return str(val).strip()
    return None


def _strlist(val: Any) -> Optional[list[str]]:
    if not isinstance(val, list):
        return None
    cleaned = [str(v).strip() for v in val if v and str(v).strip().lower() not in ("null", "none", "")]
    return cleaned or None


def _date(val: Any) -> Optional[date]:
    if not val or str(val).strip().lower() in ("null", "none", ""):
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%m/%d/%Y", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse date: %r", s)
    return None
