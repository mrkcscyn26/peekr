"""C5 TXT extractor. Implements F2, F5. Covers FR-4, FR-5. Built in T-03.

Try utf-8, then utf-8-sig, then cp1252; parts of about 3000 characters, location 'part N'.
"""

from __future__ import annotations

from app.indexing.extractors import Segment, group_parts


def decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return data.decode(enc).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue
    return data.decode("cp1252", errors="replace")


def extract(path: str) -> list[Segment]:
    with open(path, "rb") as fh:
        text = decode(fh.read())
    return group_parts(text.replace("\r\n", "\n").split("\n\n"))
