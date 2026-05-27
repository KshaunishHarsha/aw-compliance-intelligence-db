import re


def clean_text(text: str) -> str:
    """Normalize extracted text: fix line endings, collapse whitespace, remove OCR noise."""
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Fix OCR hyphenation artifacts: "word-\nnext" → "wordnext"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Collapse runs of spaces/tabs (preserves newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Collapse more than two consecutive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip control characters except newline and tab
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)

    return text.strip()
