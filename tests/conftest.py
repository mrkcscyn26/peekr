"""Shared fixtures. Every test runs with outbound network blocked (FR-22, FR-23):
any socket connection to a non-loopback address raises, so a hidden network call fails the test."""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import ipaddress  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.ai.embedder import Embedder  # noqa: E402
from app.ai.llm import LLMUnavailable  # noqa: E402
from app.core.config import load_config  # noqa: E402

OUTBOUND_ATTEMPTS: list = []
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _is_loopback(address) -> bool:
    if isinstance(address, tuple) and address:
        host = address[0]
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
    return True  # AF_UNIX and socketpair internals


def _guard(fn):
    def wrapper(self, address):
        if not _is_loopback(address):
            OUTBOUND_ATTEMPTS.append(address)
            raise ConnectionRefusedError(f"outbound network blocked in tests: {address}")
        return fn(self, address)
    return wrapper


socket.socket.connect = _guard(_real_connect)
socket.socket.connect_ex = _guard(_real_connect_ex)


@pytest.fixture(scope="session", autouse=True)
def no_outbound_network():
    yield
    assert OUTBOUND_ATTEMPTS == [], f"outbound connections attempted: {OUTBOUND_ATTEMPTS}"


class FakeLLM:
    """Stands in for C12. Set .down = True to simulate Ollama being stopped."""

    def __init__(self, model: str = "fake-model:1b") -> None:
        self.model = model
        self.calls = 0
        self.down = False

    def chat(self, system: str, user: str) -> str:
        if self.down:
            raise LLMUnavailable("ConnectError")
        self.calls += 1
        return f"Summary #{self.calls} of {user.splitlines()[0]}"

    def list_models(self, timeout: float = 2.0) -> list[str]:
        if self.down:
            raise LLMUnavailable("ConnectError")
        return [self.model]

    def model_installed(self, names: list[str]) -> bool:
        return self.model in names


def make_cfg(data_dir: Path, **overrides):
    base = {"data_dir": str(data_dir), "ollama.url": "http://127.0.0.1:1", "watcher.debounce_seconds": 0.5,
            "watcher.move_window_seconds": 2}
    base.update(overrides)
    return load_config(overrides=base)


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    e = Embedder(load_config().embedding)
    e.load()
    assert e.ready.is_set(), e.error
    return e


@pytest.fixture(scope="session")
def demo_src(tmp_path_factory) -> Path:
    from make_demo_data import build

    root = tmp_path_factory.mktemp("demo_src") / "demo"
    build(root)
    return root


def copy_tree(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst, copy_function=shutil.copy2)
    return dst


def wait_job(client, timeout: float = 300) -> dict:
    ctx = client.app.state.ctx
    assert ctx.indexer.wait_idle(timeout), "indexer did not become idle"
    return client.get("/api/index/status").json()


def wait_for(fn, timeout: float = 15, interval: float = 0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(interval)
    return fn()
