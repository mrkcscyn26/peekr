"""C3 Core. Supports F1, F2, F3, F4, F5, F6, F7. Covers FR-3, FR-23, FR-24. Built in T-01.

Logs go to data/logs. Log events, ids, paths and timings only, never file text,
summaries or search queries (Section 8.11).
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    root = logging.getLogger("peekr")
    root.setLevel(level)
    log_file = str(Path(logs_dir) / "peekr.log")
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler) and h.baseFilename == str(Path(log_file).resolve()):
            return
        root.removeHandler(h)
        h.close()
    fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter(_FORMAT))
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(fh)
    root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"peekr.{name}")
