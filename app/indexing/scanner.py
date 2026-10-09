"""C4 Scanner. Implements F2, F6. Covers FR-1, FR-3, FR-7, FR-19. Built in T-03.

Read-only: only os.walk and os.stat are used on user folders (FR-3).
Assumption (flagged): files over indexing.max_file_size_mb are still yielded so the
indexer can record them as skipped with reason too_large and list them (FR-5).
"""

from __future__ import annotations

import fnmatch
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from app.core.config import Section, is_within, norm_path, ts_to_iso


@dataclass(frozen=True)
class ScanEntry:
    path: str
    name: str
    extension: str
    size: int
    created_at: str
    modified_at: str


def _ignored(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _hidden(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM)) if attrs else False


def is_candidate_name(name: str, indexing: Section) -> bool:
    """Supported extension and not a temporary or hidden name (also used by C15)."""
    return Path(name).suffix.lower() in indexing.supported_extensions and not _ignored(name, indexing.ignore_patterns)


def entry_for(path: str, st: os.stat_result | None = None) -> ScanEntry:
    st = st or os.stat(path)
    p = Path(path)
    return ScanEntry(
        path=path, name=p.name, extension=p.suffix.lower(), size=st.st_size,
        created_at=ts_to_iso(getattr(st, "st_birthtime", st.st_ctime)), modified_at=ts_to_iso(st.st_mtime),
    )


def scan(folder: str, indexing: Section, excluded: Iterable[str] = ()) -> Iterator[ScanEntry]:
    """Walk folder recursively and yield candidate files (F2 step 4, F6 step 1)."""
    excluded = [norm_path(e) for e in excluded]
    patterns = indexing.ignore_patterns
    for root, dirs, files in os.walk(folder, onerror=lambda e: None):
        kept = []
        for d in dirs:
            full = os.path.join(root, d)
            if _ignored(d, patterns) or any(is_within(full, e) for e in excluded):
                continue
            try:
                if _hidden(os.stat(full)):
                    continue
            except OSError:
                continue
            kept.append(d)
        dirs[:] = kept
        for name in files:
            if not is_candidate_name(name, indexing):
                continue
            full = norm_path(os.path.join(root, name))
            if any(is_within(full, e) for e in excluded):
                continue
            try:
                st = os.stat(full)
            except OSError:
                continue
            if _hidden(st) or not stat.S_ISREG(st.st_mode):
                continue
            yield entry_for(full, st)
