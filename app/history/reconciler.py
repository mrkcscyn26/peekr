"""C16 Reconciler. Implements F1, F6. Covers FR-19. Built in T-10.

Compares disk (via C4) with the files table and classifies every file as unchanged,
touched (same hash, new times), modified, retry (pending or error), moved or renamed,
created, deleted, or excluded (F6 steps 1-6). It only reads; the C8 worker applies
the plan. Moves are matched by content_hash across all folders in the job.
A missing folder is reported as unavailable and its files are never marked deleted.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Callable

from app.core.config import Section, is_within
from app.db import repo
from app.indexing.scanner import ScanEntry, scan

BLOCK = 1024 * 1024


def file_hash(path: str, retry_delay: float = 1.0) -> str:
    """SHA-256 over the file bytes in 1 MB blocks. A locked file is retried once after 1 second."""
    for attempt in (0, 1):
        try:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for block in iter(lambda: fh.read(BLOCK), b""):
                    h.update(block)
            return h.hexdigest()
        except PermissionError:
            if attempt:
                raise
            time.sleep(retry_delay)
    raise AssertionError("unreachable")


def try_hash(path: str) -> str | None:
    try:
        return file_hash(path)
    except OSError:
        return None


@dataclass
class Item:
    entry: ScanEntry
    folder_id: int
    row: dict | None = None
    hash: str | None = None


@dataclass
class Plan:
    unchanged: list[Item] = field(default_factory=list)
    touched: list[Item] = field(default_factory=list)
    modified: list[Item] = field(default_factory=list)
    retry: list[Item] = field(default_factory=list)
    moves: list[Item] = field(default_factory=list)  # item.row is the old row
    created: list[Item] = field(default_factory=list)
    deleted: list[dict] = field(default_factory=list)
    excluded: list[dict] = field(default_factory=list)
    unavailable: list[int] = field(default_factory=list)

    @property
    def disk_count(self) -> int:
        return sum(len(x) for x in (self.unchanged, self.touched, self.modified, self.retry, self.moves, self.created))


def build_plan(conn: sqlite3.Connection, folders: list[dict], indexing: Section,
               progress: Callable[[str], None] = lambda p: None) -> Plan:
    plan = Plan()
    created: list[Item] = []
    missing: list[dict] = []
    for folder in folders:
        if not os.path.isdir(folder["path"]):
            plan.unavailable.append(folder["id"])
            continue
        excluded = [e["path"] for e in repo.list_exclusions(conn, folder["id"])]
        disk = {e.path: e for e in scan(folder["path"], indexing, excluded)}
        rows = {r["current_path"]: r for r in repo.list_files(conn, folder_id=folder["id"])}
        for path, row in rows.items():
            if row["status"] == "deleted" or path in disk:
                continue
            if any(is_within(path, e) for e in excluded):
                plan.excluded.append(row)
            else:
                missing.append(row)
        for path, entry in disk.items():
            row = rows.get(path)
            if row is None or row["status"] == "deleted":
                progress(path)
                created.append(Item(entry, folder["id"], row, try_hash(path)))
            elif row["status"] in ("pending", "error"):
                plan.retry.append(Item(entry, folder["id"], row, try_hash(path)))
            elif row["size_bytes"] == entry.size and row["modified_at"] == entry.modified_at:
                plan.unchanged.append(Item(entry, folder["id"], row, row["content_hash"]))
            else:
                progress(path)
                h = try_hash(path)
                item = Item(entry, folder["id"], row, h)
                (plan.touched if h is not None and h == row["content_hash"] else plan.modified).append(item)
    by_hash: dict[str, list[dict]] = {}
    for row in missing:
        if row["content_hash"]:
            by_hash.setdefault(row["content_hash"], []).append(row)
    for item in created:
        candidates = by_hash.get(item.hash or "", [])
        if candidates:
            old = candidates.pop(0)
            plan.moves.append(Item(item.entry, item.folder_id, old, item.hash))
            missing.remove(old)
        else:
            plan.created.append(item)
    plan.deleted = missing
    return plan
