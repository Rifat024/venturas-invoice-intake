"""Turn a file on disk into something the LLM can read.

Every document is rendered to one or more page images (a single, robust path
that also handles scans and image-only PDFs). When a PDF carries a real text
layer we also pull that text and pass it alongside the image as a high-quality
hint. Heavy libraries are imported lazily so --offline mode and the unit tests
need none of them installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
# A PDF with fewer than this many extractable characters is treated as a scan.
_TEXT_LAYER_MIN_CHARS = 40


@dataclass
class Document:
    source_file: str
    page_images: List[bytes] = field(default_factory=list)   # PNG bytes per page
    text_layer: Optional[str] = None                          # None if scanned
    kind: str = "image"                                       # image | pdf_text | pdf_scan

    @property
    def mime(self) -> str:
        return "image/png"


def load_document(path: str, dpi: int = 200) -> Document:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in IMAGE_EXTS:
        return Document(source_file=p.name, page_images=[p.read_bytes()], kind="image")
    if ext == ".pdf":
        return _load_pdf(p, dpi=dpi)
    raise ValueError(f"Unsupported file type: {p.name}")


def _load_pdf(p: Path, dpi: int) -> Document:
    import fitz  # PyMuPDF, imported lazily

    text_parts: List[str] = []
    images: List[bytes] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(p) as doc:
        for page in doc:
            text_parts.append(page.get_text("text") or "")
            images.append(page.get_pixmap(matrix=matrix).tobytes("png"))
    text = "\n".join(text_parts).strip()
    has_text = len(text) >= _TEXT_LAYER_MIN_CHARS
    return Document(
        source_file=p.name,
        page_images=images,
        text_layer=text if has_text else None,
        kind="pdf_text" if has_text else "pdf_scan",
    )
