"""C5 DOCX extractor. Implements F2, F5. Covers FR-4, FR-5. Built in T-03.

Paragraphs and table cells in body order, grouped into parts of about 3000
characters, location 'part N'. DOCX has no reliable page numbers (Section 8.10).
"""

from __future__ import annotations

from typing import Iterator

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.indexing.extractors import Segment, check_not_encrypted_ooxml, group_parts


def _blocks(document) -> Iterator[str]:
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            yield item.text
        elif isinstance(item, Table):
            for row in item.rows:
                cells = []
                for cell in row.cells:
                    t = cell.text.strip()
                    if t and (not cells or cells[-1] != t):  # merged cells repeat their text
                        cells.append(t)
                if cells:
                    yield " | ".join(cells)


def extract(path: str) -> list[Segment]:
    check_not_encrypted_ooxml(path)
    with open(path, "rb") as fh:
        document = docx.Document(fh)
    return group_parts(_blocks(document))
