"""
Section splitter for large regulation and policy documents.

Strategy by document:
- CFR Title 9 (no PDF bookmarks): text-based Part/Subpart regex.
- AWA Blue Book (has bookmarks, en-dash typography): bookmark-based split at all levels.
  Parts 2/3 use Level-4 Subpart bookmarks; any unbookmarked Subparts fall back to text.
- APHIS Inspection Guide (has bookmarks): Level-1 bookmark = chapter boundary.

`split_into_sections` accepts optional `file_bytes` (the raw PDF) so the caller can
pass it for bookmark-based splitting without an extra download.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_MIN_SECTION_CHARS = 500

# Subpart header — handles both em-dash (CFR, no spaces) and en-dash (Blue Book, with spaces)
_SUBPART_RE = re.compile(r"^(Subpart [A-Z])\s*[—–]\s*(.{3,80})$", re.MULTILINE)
# Part header — CFR uses em-dash only
_PART_RE = re.compile(r"^(PART \d+)—(.{3,80})$", re.MULTILINE)

# Only AWA-relevant CFR parts (others in Title 9 are livestock disease, biologics, etc.)
_AWA_PART_NUMBERS = {1, 2, 3, 4, 11}


@dataclass
class Section:
    title: str
    text: str
    section_index: int


def split_into_sections(
    text: str,
    doc_type: str,
    file_bytes: Optional[bytes] = None,
) -> list[Section]:
    """
    Split a large regulation or policy document into searchable sections.
    Returns an empty list when splitting is not applicable.
    """
    if doc_type == "regulation":
        sections = _split_regulation(text, file_bytes)
    elif doc_type == "policy":
        sections = _split_policy(file_bytes) if file_bytes else []
    else:
        return []

    return [s for s in sections if len(s.text.strip()) >= _MIN_SECTION_CHARS]


# ── Regulation ────────────────────────────────────────────────────────────────

def _split_regulation(text: str, file_bytes: Optional[bytes]) -> list[Section]:
    if file_bytes:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        toc = doc.get_toc()
        if toc:
            return _split_bluebook_by_toc(doc, toc)
    # CFR Title 9 has no PDF bookmarks — use text-based regex
    return _split_cfr_by_text(text)


def _split_cfr_by_text(text: str) -> list[Section]:
    """
    Split CFR Title 9 at Subpart level within each AWA-relevant Part.
    Parts without Subparts (Part 1 — Definitions) are kept whole.

    Deduplication strategy: the CFR PDF produces two copies of each header —
    one in the compact per-Part table-of-contents and one in the body text.
    For Parts: keep FIRST occurrence of each Part number (the TOC entry comes
    AFTER the body in CFR layout, so first is body). For Subparts: keep LAST
    occurrence of each letter (the body always follows the per-Part mini-TOC).
    """
    all_parts = list(_PART_RE.finditer(text))
    seen_parts: dict[int, re.Match] = {}
    for m in all_parts:
        n = int(re.search(r"\d+", m.group(1)).group())
        if n in _AWA_PART_NUMBERS and n not in seen_parts:
            seen_parts[n] = m

    awa_matches = sorted(seen_parts.values(), key=lambda m: m.start())
    if not awa_matches:
        return []

    sections: list[Section] = []
    idx = 0

    for i, pm in enumerate(awa_matches):
        part_num = int(re.search(r"\d+", pm.group(1)).group())
        part_label = f"Part {part_num}"
        part_title = pm.group(2).strip().rstrip("-").strip()
        part_start = pm.start()
        part_end = awa_matches[i + 1].start() if i + 1 < len(awa_matches) else len(text)
        part_text = text[part_start:part_end]

        sub_sections = _split_part_by_subpart(part_text, part_label, first_wins=False)
        if sub_sections:
            for ss in sub_sections:
                ss.section_index = idx
                sections.append(ss)
                idx += 1
        else:
            sections.append(Section(
                title=f"{part_label} — {part_title}",
                text=part_text,
                section_index=idx,
            ))
            idx += 1

    return sections


def _split_bluebook_by_toc(doc, toc: list) -> list[Section]:
    """
    AWA Blue Book bookmark-based split.

    Level structure:
      L2: Introduction, Animal Welfare Act As of Jan. 1, 2020,
          Animal Welfare Regulations As of Jan. 1, 2020, INDEX
      L3: ANIMAL WELFARE ACT (statute), PART 1, PART 2, PART 3
      L4: § 2131... (statute sections), § 1.1 (Part 1 defs),
          Subpart A–J (Part 2), Subpart A (Part 3 — incomplete)

    We build sections from top-level blocks + Level-4 Subpart bookmarks.
    Part 3 Subparts not in the bookmark list fall back to text-based splitting.
    """
    # Index page boundaries from L2/L3 entries we care about
    # Collect all Subpart L4 bookmark entries
    subpart_bm: list[tuple[str, int]] = [
        (title.strip(), page)
        for level, title, page in toc
        if level == 4 and title.strip().startswith("Subpart")
    ]

    # Find the INDEX/appendix page — hard stop for all Part content extraction.
    # The Blue Book ends with an INDEX at the last L2 entry before the page count.
    index_page = next(
        (p for level, t, p in toc if level == 2 and "INDEX" in t.upper()),
        doc.page_count + 1,
    )

    # Determine Part page ranges from L3 TOC entries, capped at index_page
    l3_entries = [(title.strip(), page) for level, title, page in toc if level == 3]
    part_ranges: dict[str, tuple[int, int]] = {}
    part_keys = ["PART 1", "PART 2", "PART 3"]
    for i, (title, start) in enumerate(l3_entries):
        for pk in part_keys:
            if title.startswith(pk):
                # End = next L3 Part entry, or index_page if none
                next_page = index_page
                for j in range(i + 1, len(l3_entries)):
                    if any(l3_entries[j][0].startswith(pk2) for pk2 in part_keys):
                        next_page = min(next_page, l3_entries[j][1])
                        break
                part_ranges[pk] = (start, next_page)

    def page_text(start_p: int, end_p: int) -> str:
        return "\n".join(
            doc[p].get_text()
            for p in range(start_p - 1, min(end_p - 1, doc.page_count))
        )

    sections: list[Section] = []
    idx = 0

    # -- Introduction --
    intro_entry = next(((t, p) for _, t, p in toc if t.strip() == "Introduction"), None)
    awa_act_entry = next(
        ((t, p) for _, t, p in toc if "Animal Welfare Act As of" in t), None
    )
    if intro_entry:
        end = awa_act_entry[1] if awa_act_entry else (part_ranges.get("PART 1", (50, 50))[0])
        sections.append(Section("Introduction", page_text(intro_entry[1], end), idx)); idx += 1

    # -- AWA statute (ANIMAL WELFARE ACT, L3) --
    awa_statute = next((p for _, t, p in toc if t.strip() == "ANIMAL WELFARE ACT"), None)
    if awa_statute:
        end = part_ranges.get("PART 1", (awa_statute + 30, 0))[0]
        sections.append(Section(
            "Animal Welfare Act (Statute)", page_text(awa_statute, end), idx
        )); idx += 1

    # -- Part 1: keep whole --
    if "PART 1" in part_ranges:
        s, e = part_ranges["PART 1"]
        sections.append(Section("PART 1 – DEFINITION OF TERMS", page_text(s, e), idx)); idx += 1

    # -- Part 2: use Level-4 Subpart bookmarks --
    if "PART 2" in part_ranges:
        p2_start, p2_end = part_ranges["PART 2"]
        p2_subparts = [(t, p) for t, p in subpart_bm if p2_start <= p < p2_end]
        for i, (title, sp) in enumerate(p2_subparts):
            ep = p2_subparts[i + 1][1] if i + 1 < len(p2_subparts) else p2_end
            sections.append(Section(
                f"PART 2 – REGULATIONS, {title}",
                page_text(sp, ep),
                idx,
            )); idx += 1
        if not p2_subparts:
            sections.append(Section(
                "PART 2 – REGULATIONS", page_text(p2_start, p2_end), idx
            )); idx += 1

    # -- Part 3: Level-4 bookmarks are incomplete; use text-based fallback --
    if "PART 3" in part_ranges:
        p3_start, p3_end = part_ranges["PART 3"]
        p3_text = page_text(p3_start, p3_end)
        # Part 4 (Rules of Practice) has no TOC bookmark so it falls inside
        # the Part 3 page range.  Truncate at the first PART 4 header so that
        # its "Subpart A/B" entries don't win the last-occurrence deduplication.
        _part4_boundary = re.compile(r"^PART 4\s*[—–]", re.MULTILINE)
        _m = _part4_boundary.search(p3_text)
        if _m:
            p3_text = p3_text[: _m.start()]
        # Text-based split with first-wins (page headers repeat Subpart names, so
        # the first occurrence of each Subpart letter IS the actual section start)
        # first_wins=False: TOC entries (pages 117-122) appear before body entries (page 123+),
        # so "last occurrence wins" correctly selects the body section header over the TOC entry.
        # Running page headers ("Subpart A" with no dash) don't match _SUBPART_RE at all.
        sub_sections = _split_part_by_subpart(p3_text, "PART 3 – STANDARDS", first_wins=False)
        if sub_sections:
            for ss in sub_sections:
                ss.section_index = idx
                sections.append(ss)
                idx += 1
        else:
            sections.append(Section("PART 3 – STANDARDS", p3_text, idx)); idx += 1

    return sections


def _split_part_by_subpart(
    part_text: str, part_label: str, first_wins: bool = False
) -> list[Section]:
    """
    Split a Part's text by Subpart headers.

    first_wins=False (default): keep the LAST occurrence of each Subpart letter.
      Used for CFR where the body text appears after the per-Part mini-TOC.
    first_wins=True: keep the FIRST occurrence of each Subpart letter.
      Used for Blue Book page-based text where page headers repeat the Subpart
      name on every page — the first occurrence IS the actual section start.
    """
    all_subparts = list(_SUBPART_RE.finditer(part_text))
    if not all_subparts:
        return []

    seen: dict[str, re.Match] = {}
    for sm in all_subparts:
        letter = sm.group(1).split()[-1]
        if first_wins:
            if letter not in seen:
                seen[letter] = sm
        else:
            seen[letter] = sm  # last wins

    unique = sorted(seen.values(), key=lambda m: m.start())
    sections: list[Section] = []

    for j, sm in enumerate(unique):
        letter = sm.group(1).split()[-1]
        subpart_title = sm.group(2).strip().rstrip("-").strip()
        start = sm.start()
        end = unique[j + 1].start() if j + 1 < len(unique) else len(part_text)
        sections.append(Section(
            title=f"{part_label}, Subpart {letter} — {subpart_title}",
            text=part_text[start:end],
            section_index=0,  # caller reassigns
        ))

    return sections


# ── Policy ────────────────────────────────────────────────────────────────────

def _split_policy(file_bytes: bytes) -> list[Section]:
    """
    APHIS Inspection Guide: Level-1 PDF bookmarks = chapter boundaries.
    """
    import fitz

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    toc = doc.get_toc()
    chapters = [(title.strip(), page) for level, title, page in toc if level == 1]
    if not chapters:
        return []

    sections: list[Section] = []
    for i, (title, start_page) in enumerate(chapters):
        end_page = chapters[i + 1][1] if i + 1 < len(chapters) else doc.page_count + 1
        pages_text = "\n".join(
            doc[p].get_text()
            for p in range(start_page - 1, min(end_page - 1, doc.page_count))
        )
        sections.append(Section(title=title, text=pages_text, section_index=i))

    return sections
