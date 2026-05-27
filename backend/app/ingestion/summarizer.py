import logging

from app.config import get_settings
from app.llm import get_llm_client

logger = logging.getLogger(__name__)
settings = get_settings()

_PROMPT = """\
Write a concise, human-readable summary of this USDA APHIS animal welfare document \
that helps an investigator or researcher quickly understand what the document contains \
and decide whether it is relevant to their search.

RULES:
- 3–5 sentences of clear prose. No bullet points, no keyword lists.
- Lead with the most important facts: facility name, location/state, date, \
document type, and the primary violation or subject.
- Name specific CFR sections cited (e.g. 9 CFR §2.40, §3.11) but do not \
list them exhaustively — focus on the key issues.
- Include species involved, certificate or docket number, and inspector name \
when present.
- Use plain language that an advocate or journalist could read, not technical jargon.
- Do NOT draw legal conclusions or call anything a confirmed violation.
- Do NOT include Latin species names — use common names only.

EXAMPLES by document type:

inspection_report:
"Routine USDA APHIS inspection of Jaws and Paws Sanctuary (cert. 93-C-1234, CA) on \
October 5 2023 identified concerns with attending veterinarian oversight under \
9 CFR §2.40 and inadequate housing conditions under §3.125(a) for the facility's \
dogs and wolf-dogs. Inspectors noted that a written program of veterinary care had \
not been established. A correction deadline of November 4 2023 was set."

enforcement_action:
"USDA APHIS consent decision against respondent John Smith (FL) under AWA Docket \
No. 25-J-0069, resolving alleged violations involving inadequate veterinary care \
and unsanitary housing for approximately 40 dogs at a licensed breeding facility. \
The respondent agreed to a $12,000 civil penalty and a 30-day suspension of their \
AWA license."

regulation:
"This section of the Animal Welfare Regulations (9 CFR Part 2, Subpart A) covers \
licensing requirements for dealers and exhibitors, including application procedures, \
fee schedules, and the conditions under which a license may be suspended or revoked."

policy:
"This chapter of the USDA APHIS Animal Care Inspection Guide describes the process \
inspectors use to assess compliance at research facilities, including how IACUC \
protocols are reviewed and how repeat violations are escalated."

Document type: {doc_type}
Document text (first 4000 characters):
{text}

Return only the summary paragraph, no preamble.\
"""


def generate_retrieval_summary(text: str, doc_type: str) -> str:
    client = get_llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_mini_model,
            messages=[{"role": "user", "content": _PROMPT.format(doc_type=doc_type, text=text[:4000])}],
            max_tokens=300,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("summarizer failed: %s", exc)
        return ""
