import io
import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

_MIN_NATIVE_CHARS = 100


def extract_text(file_bytes: bytes, mime_type: str) -> str:
    """Extract raw text from a document. Falls back to Tesseract for scanned PDFs."""
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _strip_nul(_extract_docx(file_bytes))
    if mime_type == "text/plain":
        return _strip_nul(file_bytes.decode("utf-8", errors="replace"))
    return _strip_nul(_extract_pdf(file_bytes))


def _strip_nul(text: str) -> str:
    return text.replace("\x00", "")


def _extract_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text() for page in doc]
    text = "\n".join(pages)

    if len(text.strip()) < _MIN_NATIVE_CHARS:
        logger.info("Sparse native text (%d chars), switching to Tesseract OCR", len(text.strip()))
        return _ocr_pdf(doc)

    return text


def _ocr_pdf(doc: fitz.Document) -> str:
    import pytesseract
    from PIL import Image

    texts: list[str] = []
    for page in doc:
        # 2x scale improves OCR accuracy on low-res scans
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        texts.append(pytesseract.image_to_string(img))

    return "\n".join(texts)


def _extract_docx(file_bytes: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs)
