"""C5 PDF extractor. Implements F2, F5. Covers FR-4, FR-5. Built in T-03.

One segment per page, location 'page N' (Section 8.10).
"""

from __future__ import annotations

import pypdfium2 as pdfium

from app.indexing.extractors import ExtractError, Segment


def extract(path: str) -> list[Segment]:
    try:
        doc = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise ExtractError("password_protected") from exc
        raise ExtractError("extract_failed", "PdfiumError") from exc
    try:
        segments = []
        for i in range(len(doc)):
            page = doc[i]
            textpage = page.get_textpage()
            try:
                segments.append(Segment(textpage.get_text_bounded(), f"page {i + 1}"))
            finally:
                textpage.close()
                page.close()
        return segments
    finally:
        doc.close()
