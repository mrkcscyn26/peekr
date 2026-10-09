"""C15 Watcher. Implements F1, F2, F5. Covers FR-18. Built in T-10.

watchdog observers per enabled folder (recursive). Events for temporary and unsupported
names are ignored, events are debounced per path (watcher.debounce_seconds), classified,
and put on the C8 queue. The watcher never touches the database (Section 8.11).
Path events are classified at flush time by checking the disk: the file exists -> upsert,
it is gone -> deleted. The C8 worker holds deletions for the move window.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.core.config import Config
from app.core.logging import get_logger
from app.indexing.pipeline import FsEvent
from app.indexing.scanner import is_candidate_name

log = get_logger("watcher")


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: "Watcher") -> None:
        self.w = watcher

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type in ("opened", "closed", "closed_no_write"):
            return
        src = os.fsdecode(event.src_path)
        dest = os.fsdecode(getattr(event, "dest_path", "") or "")
        if event.is_directory:
            if event.event_type == "deleted":
                self.w.push(("dir", src), FsEvent("deleted_dir", src), delay=0)
            elif event.event_type == "moved" and dest:
                self.w.push(("dir", dest), FsEvent("moved_dir", src, dest), delay=0)
            return
        cand = self.w.candidate
        if event.event_type == "moved" and dest:
            if cand(src):
                self.w.drop(("path", src))
                self.w.push(("path", dest), FsEvent("moved", src, dest))
            elif cand(dest):
                self.w.push(("path", dest), FsEvent("touch", dest))
            return
        if cand(src):
            self.w.push(("path", src), FsEvent("touch", src))


class Watcher:
    def __init__(self, cfg: Config, submit: Callable[[FsEvent], None]) -> None:
        self.cfg = cfg
        self.submit = submit
        self.debounce = float(cfg.watcher.debounce_seconds)
        self._observer = Observer()
        self._watches: dict[int, object] = {}
        self._pending: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._flusher = threading.Thread(target=self._flush_loop, name="watcher-flush", daemon=True)
        self._started = False

    def candidate(self, path: str) -> bool:
        return is_candidate_name(os.path.basename(path), self.cfg.indexing)

    def start(self) -> None:
        if not self._started:
            self._observer.start()
            self._flusher.start()
            self._started = True

    def watch(self, folder_id: int, path: str) -> bool:
        self.start()
        with self._lock:
            if folder_id in self._watches:
                return True
        if not os.path.isdir(path):
            return False
        try:
            handle = self._observer.schedule(_Handler(self), path, recursive=True)
        except OSError as exc:
            log.warning("watch failed folder_id=%s error=%s", folder_id, type(exc).__name__)
            return False
        with self._lock:
            self._watches[folder_id] = handle
        log.info("watching folder_id=%s", folder_id)
        return True

    def unwatch(self, folder_id: int) -> None:
        with self._lock:
            handle = self._watches.pop(folder_id, None)
        if handle is not None:
            try:
                self._observer.unschedule(handle)
            except (KeyError, OSError):
                pass

    def watching(self) -> list[int]:
        with self._lock:
            return list(self._watches)

    def stop(self) -> None:
        self._stop.set()
        if self._started:
            self._observer.stop()
            self._observer.join(5)
            self._flusher.join(2)

    # ---- debounce ----

    def push(self, key: tuple, event: FsEvent, delay: float | None = None) -> None:
        due = time.monotonic() + (self.debounce if delay is None else delay)
        with self._lock:
            prev = self._pending.pop(key, None)
            if prev and prev[0].kind == "moved" and event.kind == "touch":
                event = prev[0]  # keep the move; C8 re-checks content after applying it
            self._pending[key] = (event, due)

    def drop(self, key: tuple) -> None:
        with self._lock:
            self._pending.pop(key, None)

    def _flush_loop(self) -> None:
        while not self._stop.wait(0.2):
            now = time.monotonic()
            ready = []
            with self._lock:
                for key, (event, due) in list(self._pending.items()):
                    if due <= now:
                        ready.append(event)
                        del self._pending[key]
            for event in ready:
                if event.kind == "touch":
                    event = FsEvent("upsert" if os.path.exists(event.path) else "deleted", event.path)
                self.submit(event)
