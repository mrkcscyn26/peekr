"""C3 Core. Supports F1, F2, F3, F4, F5, F6, F7. Covers FR-3, FR-23, FR-24. Built in T-01."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


class ConfigError(ValueError):
    pass


class Section(dict):
    """Dict with attribute access for nested config sections."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _wrap(value: Any) -> Any:
    if isinstance(value, dict):
        return Section({k: _wrap(v) for k, v in value.items()})
    return value


class Config(Section):
    @property
    def data_path(self) -> Path:
        return Path(self["data_dir"])

    @property
    def db_path(self) -> Path:
        return self.data_path / "peekr.db"

    @property
    def logs_path(self) -> Path:
        return self.data_path / "logs"


def validate(cfg: Config) -> None:
    """Enforce hard rules 2 and 4: loopback server and local Ollama, no cloud model tags."""
    if cfg.server.host != "127.0.0.1":
        raise ConfigError("server.host must be 127.0.0.1 (FR-24)")
    if urlparse(cfg.ollama.url).hostname not in LOOPBACK_HOSTS:
        raise ConfigError("ollama.url must point to 127.0.0.1 (hard rule 4)")
    model = str(cfg.llm.model)
    if model.endswith(":cloud") or model.endswith("-cloud"):
        raise ConfigError("cloud model tags are not allowed (hard rule 4)")


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> Config:
    """Load config.yaml, apply overrides, resolve data_dir and create data and log folders (F1 step 2)."""
    path = Path(path or os.environ.get("PEEKR_CONFIG") or PROJECT_ROOT / "config.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for dotted, value in (overrides or {}).items():
        node = raw
        *parents, leaf = dotted.split(".")
        for key in parents:
            node = node.setdefault(key, {})
        node[leaf] = value
    if os.environ.get("PEEKR_DATA_DIR"):
        raw["data_dir"] = os.environ["PEEKR_DATA_DIR"]
    data_dir = Path(raw.get("data_dir", "./data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    raw["data_dir"] = str(data_dir.resolve())
    cfg = Config(_wrap(raw))
    validate(cfg)
    cfg.data_path.mkdir(parents=True, exist_ok=True)
    cfg.logs_path.mkdir(parents=True, exist_ok=True)
    return cfg


def norm_path(path: str | Path) -> str:
    """Absolute, normalized path string used for every stored path."""
    return str(Path(path).resolve())


def is_within(path: str | Path, folder: str | Path) -> bool:
    """Case-insensitive on Windows: True when path equals folder or is inside it."""
    p = os.path.normcase(os.path.normpath(str(path)))
    f = os.path.normcase(os.path.normpath(str(folder)))
    return p == f or p.startswith(f.rstrip("\\/") + os.sep)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ts_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")
