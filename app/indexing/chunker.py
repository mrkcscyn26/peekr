"""C6 Chunker. Implements F2, F5. Covers FR-4, FR-7. Built in T-04.

Rules (Section 8.10): chunks never cross a segment (page or slide) boundary; split at
paragraph or line breaks, then sentences, merge up to target_chars, carry overlap_chars
into the next chunk; short segments become one chunk; never an empty chunk.
Assumption (flagged): a trailing piece shorter than min_chunk_chars is merged into the
previous chunk of the same segment, so a chunk may exceed target_chars slightly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.core.config import Section
from app.indexing.extractors import Segment

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    index: int
    location: str
    text: str


def _pieces(text: str, target: int) -> list[str]:
    """Split text into pieces no longer than target, preferring paragraph, line, then sentence breaks."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= target:
            out.append(para)
            continue
        for line in para.split("\n"):
            line = line.strip()
            if not line:
                continue
            if len(line) <= target:
                out.append(line)
                continue
            for sent in _SENTENCE.split(line):
                while len(sent) > target:
                    cut = sent.rfind(" ", 0, target)
                    cut = cut if cut > target // 2 else target
                    out.append(sent[:cut].strip())
                    sent = sent[cut:].strip()
                if sent:
                    out.append(sent)
    return out


def _tail(text: str, n: int) -> str:
    if n <= 0 or len(text) <= n:
        return "" if n <= 0 else text
    tail = text[-n:]
    space = tail.find(" ")
    return tail[space + 1:] if 0 <= space < len(tail) - 1 else tail


def _split_segment(text: str, target: int, overlap: int, min_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= target:
        return [text]
    chunks: list[str] = []
    cur = ""
    for piece in _pieces(text, target):
        if cur and len(cur) + 1 + len(piece) > target:
            chunks.append(cur)
            carry = _tail(cur, overlap)
            cur = f"{carry} {piece}".strip() if carry and len(carry) + 1 + len(piece) <= target else piece
        else:
            cur = f"{cur}\n{piece}" if cur else piece
    if cur:
        if chunks and len(cur) < min_chars:
            chunks[-1] = f"{chunks[-1]}\n{cur}"
        else:
            chunks.append(cur)
    return [c for c in chunks if c.strip()]


def chunk_segments(segments: Iterable[Segment], chunking: Section) -> list[Chunk]:
    out: list[Chunk] = []
    for seg in segments:
        for text in _split_segment(seg.text, chunking.target_chars, chunking.overlap_chars, chunking.min_chunk_chars):
            out.append(Chunk(len(out), seg.location, text))
    return out
