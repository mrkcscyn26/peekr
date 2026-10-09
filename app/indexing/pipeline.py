"""C8 Indexer. Implements F2, F5, F6. Covers FR-1, FR-3, FR-6, FR-7, FR-19. Built in T-05.

One worker thread owns a FIFO queue of jobs (initial or rescan) and watcher events and
is the only writer of files, chunks and events (Section 8.11). One file is processed
per transaction. A bad file never stops a job (hard rule 9). User files are only read.

Assumptions (flagged):
- New files get a baseline event while their folder has never finished a scan
  (folders.last_scan_at is NULL), otherwise a created event. Initial jobs use source
  'scan'; rescans and the startup reconciliation use 'reconcile'; watcher events use 'watcher'.
- Both job kinds run the same reconciliation plan (C16), so an initial job on a folder
  that was already indexed only processes new or changed files (FR-7).
- Files under a newly excluded subfolder are removed from the index (FR-2), not marked deleted.
"""

from __future__ import annotations

import itertools
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.ai.embedder import Embedder, to_bytes
from app.core.config import Config, is_within, utc_now
from app.core.logging import get_logger
from app.db import repo
from app.db.connection import connect, transaction
from app.history import events as history
from app.history.reconciler import Item, build_plan, file_hash, try_hash
from app.indexing.chunker import chunk_segments
from app.indexing.extractors import ExtractError, extract
from app.indexing.scanner import ScanEntry, entry_for, is_candidate_name
from app.services.category import CategoryService

log = get_logger("indexer")

_STOP = object()


@dataclass
class Job:
    id: int
    kind: str
    folder_ids: list[int] | None
    state: str = "queued"
    total: int = 0
    processed: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    current_file: str | None = None
    skipped_items: list[dict] = field(default_factory=list)
    unavailable_folders: list[int] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"job_id": self.id, "kind": self.kind, "state": self.state, "total": self.total,
                "processed": self.processed, "unchanged": self.unchanged, "skipped": self.skipped,
                "errors": self.errors, "current_file": self.current_file, "skipped_items": list(self.skipped_items),
                "unavailable_folders": list(self.unavailable_folders), "error": self.error}


@dataclass(frozen=True)
class FsEvent:
    """Classified watcher event (C15): upsert, deleted, moved, deleted_dir, moved_dir."""
    kind: str
    path: str
    dest: str | None = None


class Indexer:
    def __init__(self, cfg: Config, db_path: str, embedder: Embedder, category: CategoryService,
                 on_change: Callable[[], None] = lambda: None,
                 on_folder_scanned: Callable[[dict], None] = lambda f: None) -> None:
        self.cfg = cfg
        self.db_path = db_path
        self.embedder = embedder
        self.category = category
        self.on_change = on_change
        self.on_folder_scanned = on_folder_scanned
        self.max_bytes = int(cfg.indexing.max_file_size_mb) * 1024 * 1024
        self.move_window = float(cfg.watcher.move_window_seconds)
        self.queue: queue.Queue = queue.Queue()
        self.jobs: dict[int, Job] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._pending_deletes: dict[str, tuple[float, int, str | None]] = {}  # path -> (deadline, file_id, hash)
        self._removed_folders: set[int] = set()
        self._prepared = False
        self.idle = threading.Event()
        self.idle.set()

    # ---- public API (called from request handlers and the watcher) ----

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="index-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self.queue.put(_STOP)
        if self._thread:
            self._thread.join(timeout)

    def submit_job(self, folder_ids: list[int] | None = None, kind: str = "initial") -> int:
        with self._lock:
            job = Job(next(self._ids), kind, folder_ids)
            self.jobs[job.id] = job
        self.idle.clear()
        self.queue.put(job)
        return job.id

    def submit_event(self, event: FsEvent) -> None:
        self.idle.clear()
        self.queue.put(event)

    def forget_folder(self, folder_id: int) -> None:
        self._removed_folders.add(folder_id)

    def status(self) -> dict[str, Any]:
        with self._lock:
            jobs = list(self.jobs.values())
        for state in ("running", "queued"):
            active = [j for j in jobs if j.state == state]
            if active:
                return active[0].as_dict()
        if jobs:
            return jobs[-1].as_dict()
        return {**Job(0, "none", None, state="idle").as_dict(), "job_id": None}

    def wait_idle(self, timeout: float = 120.0) -> bool:
        """Block until the queue is drained (tests and scripts)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.idle.wait(0.1) and self.queue.empty() and not self._pending_deletes:
                return True
        return False

    # ---- worker ----

    def _run(self) -> None:
        conn = connect(self.db_path)
        try:
            while True:
                timeout = 0.5
                if self._pending_deletes:
                    timeout = max(0.05, min(d for d, _, _ in self._pending_deletes.values()) - time.monotonic())
                try:
                    item = self.queue.get(timeout=timeout)
                except queue.Empty:
                    item = None
                self._flush_deletes(conn)
                if item is _STOP:
                    break
                if item is not None:
                    self._handle(conn, item)
                if self.queue.empty() and not self._pending_deletes:
                    self.idle.set()
        finally:
            conn.close()

    def _prepare(self, conn) -> bool:
        """Wait for the embedder, store model settings, embed category labels. False if the embedder failed."""
        self.embedder.done.wait()
        if not self.embedder.ready.is_set():
            return False
        if self._prepared:
            return True
        with transaction(conn):
            model, dim = repo.get_setting(conn, "embedding_model"), repo.get_setting(conn, "embedding_dim")
            if (model, dim) != (self.embedder.model_name, str(self.embedder.dim)):
                if model is not None:
                    n = repo.reset_all_for_reembed(conn)
                    log.info("embedding model changed, %d files will be re-embedded", n)
                repo.set_setting(conn, "embedding_model", self.embedder.model_name)
                repo.set_setting(conn, "embedding_dim", str(self.embedder.dim))
            self.category.ensure_labels(conn)
        self._prepared = True
        self.on_change()
        return True

    def _handle(self, conn, item: Job | FsEvent) -> None:
        if not self._prepare(conn):
            if isinstance(item, Job):
                item.state, item.error = "failed", "embedder_not_ready"
            return
        if isinstance(item, Job):
            item.state = "running"
            try:
                self._run_job(conn, item)
                item.state = "done"
            except Exception as exc:  # noqa: BLE001 - fatal job error (for example the database is not writable)
                log.exception("job %s failed: %s", item.id, type(exc).__name__)
                item.state, item.error = "failed", "internal"
            finally:
                item.current_file = None
                self.on_change()
        else:
            try:
                self._handle_event(conn, item)
            except Exception as exc:  # noqa: BLE001
                log.exception("watcher event failed kind=%s path=%s: %s", item.kind, item.path, type(exc).__name__)
            self.on_change()

    # ---- jobs (F2, F6) ----

    def _run_job(self, conn, job: Job) -> None:
        t0 = time.perf_counter()
        folders = [f for f in repo.list_folders(conn, enabled_only=True)
                   if job.folder_ids is None or f["id"] in job.folder_ids]
        source = "scan" if job.kind == "initial" else "reconcile"

        def progress(path: str) -> None:
            job.current_file = os.path.basename(path)

        plan = build_plan(conn, folders, self.cfg.indexing, progress)
        job.unavailable_folders = plan.unavailable
        job.total = plan.disk_count
        first_scan = {f["id"]: f["last_scan_at"] is None for f in folders}
        job.unchanged = len(plan.unchanged)
        job.processed += len(plan.unchanged)

        for row in plan.excluded:
            with transaction(conn):
                repo.delete_file(conn, row["id"])
        for it in plan.touched:
            with transaction(conn):
                repo.update_file_times(conn, it.row["id"], it.entry.size, it.entry.created_at, it.entry.modified_at)
            job.processed += 1
        for it in plan.moves:
            with transaction(conn):
                kind = history.apply_move(conn, it.row, it.entry.path, it.folder_id, source)
                repo.update_file_times(conn, it.row["id"], it.entry.size, it.entry.created_at, it.entry.modified_at)
            log.info("%s file_id=%s", kind, it.row["id"])
            job.processed += 1
        for row in plan.deleted:
            with transaction(conn):
                history.apply_delete(conn, row, source)
            log.info("deleted file_id=%s", row["id"])
        work = [(it, "modified") for it in plan.modified]
        work += [(it, None) for it in plan.retry]
        work += [(it, "baseline" if first_scan.get(it.folder_id) else "created") for it in plan.created]
        for it, event in work:
            if it.folder_id in self._removed_folders:
                continue
            job.current_file = it.entry.name
            if event is None and it.row and it.hash and it.row["content_hash"] and it.hash != it.row["content_hash"]:
                event = "modified"
            status, reason = self._safe_index(conn, it, event, source)
            job.processed += 1
            if status in ("skipped", "error"):
                job.skipped += status == "skipped"
                job.errors += status == "error"
                job.skipped_items.append({"path": it.entry.path, "reason": reason})
        now = utc_now()
        with transaction(conn):
            for f in folders:
                if f["id"] not in plan.unavailable and f["id"] not in self._removed_folders:
                    repo.set_folder_scanned(conn, f["id"], now)
        for f in folders:
            if f["id"] not in plan.unavailable:
                self.on_folder_scanned(f)
        log.info("job %s %s done total=%d unchanged=%d skipped=%d errors=%d in %.1fs", job.id, job.kind, job.total,
                 job.unchanged, job.skipped, job.errors, time.perf_counter() - t0)

    # ---- one file (F2 steps 6-7) ----

    def _safe_index(self, conn, it: Item, event: str | None, source: str) -> tuple[str, str | None]:
        try:
            return self._index_file(conn, it, event, source)
        except Exception as exc:  # noqa: BLE001 - unexpected: mark error internal and continue (Section 8.11)
            log.error("index failed file=%s error=%s", it.entry.path, type(exc).__name__)
            try:
                with transaction(conn):
                    e = it.entry
                    repo.upsert_file(conn, folder_id=it.folder_id, path=e.path, name=e.name, extension=e.extension,
                                     size_bytes=e.size, created_at=e.created_at, modified_at=e.modified_at,
                                     content_hash=it.hash, category=None, status="error", status_reason="internal",
                                     indexed_at=None)
            except Exception:  # noqa: BLE001
                log.error("could not record error for file=%s", it.entry.path)
            return "error", "internal"

    def _index_file(self, conn, it: Item, event: str | None, source: str) -> tuple[str, str | None]:
        t0 = time.perf_counter()
        e = it.entry
        status, reason, category, rows = "indexed", None, None, []
        h = it.hash
        if h is None:
            try:
                h = file_hash(e.path)
            except PermissionError:
                status, reason = "error", "file_locked"
            except OSError:
                status, reason = "error", "extract_failed"
        if status == "indexed" and e.size > self.max_bytes:
            status, reason = "skipped", "too_large"
        if status == "indexed":
            try:
                try:
                    segments = extract(e.path)
                except PermissionError:
                    time.sleep(1.0)
                    segments = extract(e.path)
                chunks = chunk_segments(segments, self.cfg.chunking)
                if not chunks:
                    raise ExtractError("no_text")
                vecs = self.embedder.embed_passages([c.text for c in chunks])
                category = self.category.assign(vecs)
                rows = [(c.index, c.location, c.text, to_bytes(v)) for c, v in zip(chunks, vecs)]
            except ExtractError as exc:
                status = "skipped" if exc.reason in ("no_text", "password_protected") else "error"
                reason = exc.reason
            except PermissionError:
                status, reason = "error", "file_locked"
        with transaction(conn):
            fid = repo.upsert_file(conn, folder_id=it.folder_id, path=e.path, name=e.name, extension=e.extension,
                                   size_bytes=e.size, created_at=e.created_at, modified_at=e.modified_at,
                                   content_hash=h, category=category, status=status, status_reason=reason,
                                   indexed_at=utc_now() if status == "indexed" else None)
            if rows:
                repo.replace_chunks(conn, fid, rows)
            else:
                repo.delete_chunks(conn, fid)
            if event:
                before = it.row["content_hash"] if it.row and it.row["status"] != "deleted" else None
                history.record(conn, fid, event, source=source, new_path=e.path,
                               hash_before=before if event == "modified" else None, hash_after=h)
        log.info("file_id=%s status=%s reason=%s chunks=%d in %.2fs", fid, status, reason, len(rows),
                 time.perf_counter() - t0)
        return status, reason

    # ---- watcher events (F5) ----

    def _folder_for(self, conn, path: str) -> dict | None:
        for f in repo.list_folders(conn, enabled_only=True):
            if is_within(path, f["path"]) and f["id"] not in self._removed_folders:
                if any(is_within(path, x["path"]) for x in repo.list_exclusions(conn, f["id"])):
                    return None
                return f
        return None

    def _live_row(self, conn, path: str) -> dict | None:
        row = repo.get_file_by_path(conn, path)
        return row if row and row["status"] != "deleted" else None

    def _handle_event(self, conn, ev: FsEvent) -> None:
        if ev.kind == "upsert":
            self._on_upsert(conn, ev.path)
        elif ev.kind == "deleted":
            row = self._live_row(conn, ev.path)
            if row:
                self._pending_deletes[ev.path] = (time.monotonic() + self.move_window, row["id"], row["content_hash"])
        elif ev.kind == "deleted_dir":
            for row in repo.list_files(conn, exclude_deleted=True):
                if is_within(row["current_path"], ev.path):
                    self._pending_deletes[row["current_path"]] = (time.monotonic() + self.move_window, row["id"],
                                                                  row["content_hash"])
        elif ev.kind == "moved":
            self._on_moved(conn, ev.path, ev.dest)
        elif ev.kind == "moved_dir":
            for row in repo.list_files(conn, exclude_deleted=True):
                if is_within(row["current_path"], ev.path):
                    rel = os.path.relpath(row["current_path"], ev.path)
                    self._on_moved(conn, row["current_path"], os.path.join(ev.dest, rel))

    def _on_upsert(self, conn, path: str) -> None:
        folder = self._folder_for(conn, path)
        if folder is None or not os.path.isfile(path) or not is_candidate_name(os.path.basename(path),
                                                                                  self.cfg.indexing):
            return
        entry = entry_for(path)
        self._pending_deletes.pop(path, None)  # delete + create at the same path is a save, not a delete
        row = self._live_row(conn, path)
        if row and row["status"] in ("indexed", "skipped") and row["size_bytes"] == entry.size \
                and row["modified_at"] == entry.modified_at:
            return
        h = try_hash(path)
        if row:
            if h is not None and h == row["content_hash"] and row["status"] in ("indexed", "skipped"):
                with transaction(conn):
                    repo.update_file_times(conn, row["id"], entry.size, entry.created_at, entry.modified_at)
                return
            event = "modified" if row["content_hash"] and h != row["content_hash"] else None
            self._safe_index(conn, Item(entry, folder["id"], row, h), event, "watcher")
            return
        # New path: a recent delete with the same hash is a move (F5 step 4).
        for old_path, (_, fid, old_hash) in list(self._pending_deletes.items()):
            if h and old_hash == h:
                del self._pending_deletes[old_path]
                old = repo.get_file(conn, fid)
                if old and old["status"] != "deleted":
                    with transaction(conn):
                        history.apply_move(conn, old, path, folder["id"], "watcher")
                        repo.update_file_times(conn, fid, entry.size, entry.created_at, entry.modified_at)
                    return
        stale = repo.get_file_by_path(conn, path)  # a deleted row at this path is reused
        self._safe_index(conn, Item(entry, folder["id"], stale, h), "created", "watcher")

    def _on_moved(self, conn, src: str, dest: str) -> None:
        row = self._live_row(conn, src)
        if row is None:
            self._on_upsert(conn, dest)
            return
        folder = self._folder_for(conn, dest)
        if folder is None or not is_candidate_name(os.path.basename(dest), self.cfg.indexing):
            # Moved outside every indexed folder (or to an ignored name): wait for a matching create, then delete.
            self._pending_deletes[src] = (time.monotonic() + self.move_window, row["id"], row["content_hash"])
            return
        with transaction(conn):
            kind = history.apply_move(conn, row, dest, folder["id"], "watcher")
        log.info("%s file_id=%s", kind, row["id"])
        if os.path.isfile(dest):
            self._on_upsert(conn, dest)  # picks up a content change made together with the move

    def _flush_deletes(self, conn) -> None:
        now = time.monotonic()
        for path, (deadline, fid, _) in list(self._pending_deletes.items()):
            if deadline > now:
                continue
            del self._pending_deletes[path]
            row = repo.get_file(conn, fid)
            if row is None or row["status"] == "deleted" or (row["current_path"] == path and os.path.exists(path)):
                continue
            if row["current_path"] != path:
                continue  # it was moved meanwhile
            with transaction(conn):
                history.apply_delete(conn, row, "watcher")
            log.info("deleted file_id=%s", fid)
            self.on_change()
