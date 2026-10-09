"""C5 Extractors. Implements F2, F5. Covers FR-4, FR-5. Built in T-03.

extract(path) returns text segments with locations, or raises ExtractError with a
reason code from Section 8.11 (password_protected, no_text, extract_failed).
PermissionError is re-raised so the indexer can retry locked files (file_locked).
Files are opened read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

PART_CHARS = 3000  # DOCX and TXT part size from Section 8.10
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # encrypted OOXML files are OLE containers


@dataclass(frozen=True)
class Segment:
    text: str
    location: str


class ExtractError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def normalize(text: str) -> str:
    """Normalize whitespace but keep line and paragraph breaks for the chunker."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [re.sub(r"[ \t\f\v\u00a0]+", " ", ln).strip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def group_parts(blocks: Iterable[str], size: int = PART_CHARS) -> list[Segment]:
    """Group paragraphs into parts of about `size` characters, location 'part N'."""
    parts: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for block in blocks:
        block = normalize(block)
        if not block:
            continue
        if cur and cur_len + len(block) > size:
            parts.append("\n\n".join(cur))
            cur, cur_len = [], 0
        cur.append(block)
        cur_len += len(block) + 2
    if cur:
        parts.append("\n\n".join(cur))
    return [Segment(p, f"part {i}") for i, p in enumerate(parts, 1)]


def check_not_encrypted_ooxml(path: str) -> None:
    with open(path, "rb") as fh:
        if fh.read(8) == OLE_MAGIC:
            raise ExtractError("password_protected")


def _registry() -> dict[str, Callable[[str], list[Segment]]]:
    from app.indexing.extractors import docx, pdf, pptx, txt

    return {".pdf": pdf.extract, ".docx": docx.extract, ".pptx": pptx.extract, ".txt": txt.extract}


def extract(path: str) -> list[Segment]:
    ext = Path(path).suffix.lower()
    fn = _registry().get(ext)
    if fn is None:
        raise ExtractError("extract_failed", f"unsupported extension {ext}")
    try:
        segments = [Segment(normalize(s.text), s.location) for s in fn(path)]
    except (ExtractError, PermissionError):
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is a bad file, never a crash (hard rule 9)
        raise ExtractError("extract_failed", type(exc).__name__) from exc
    segments = [s for s in segments if s.text]
    if not segments:
        raise ExtractError("no_text")
    return segments
