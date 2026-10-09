"""C12 LLM client. Implements F1, F4. Covers FR-14, FR-15, FR-22. Built in T-09.

Talks only to the local Ollama server (config validates a loopback URL). One global
lock so a single LLM call runs at a time (Section 8.5, 8.11). Thinking mode is turned
off with the Ollama think option; if the server rejects it, the call is retried
without it and with Qwen3's /no_think switch.
"""

from __future__ import annotations

import re
import threading
import time

import httpx

from app.core.config import Section
from app.core.logging import get_logger

log = get_logger("llm")
_LLM_LOCK = threading.Lock()
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, ollama: Section, llm: Section) -> None:
        self.url = ollama.url.rstrip("/")
        self.model: str = llm.model
        self.temperature = float(llm.temperature)
        self.num_ctx = int(llm.num_ctx)
        self.num_predict = int(llm.num_predict)
        self.timeout = float(llm.timeout_seconds)
        self.disable_thinking = bool(llm.disable_thinking)

    def list_models(self, timeout: float = 2.0) -> list[str]:
        """Installed local model names. Raises LLMUnavailable if Ollama does not answer."""
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=timeout)
            r.raise_for_status()
            return [m.get("name") or m.get("model") for m in r.json().get("models", [])]
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailable(type(exc).__name__) from exc

    def model_installed(self, names: list[str]) -> bool:
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return wanted in names

    def chat(self, system: str, user: str) -> str:
        body: dict = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx, "num_predict": self.num_predict},
        }
        if self.disable_thinking:
            body["think"] = False
        with _LLM_LOCK:
            t0 = time.perf_counter()
            try:
                r = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
                if r.status_code == 400 and "think" in r.text.lower() and "think" in body:
                    body.pop("think")
                    body["messages"][1]["content"] = f"{user}\n/no_think"
                    r = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
                r.raise_for_status()
                content = r.json()["message"]["content"]
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                log.warning("llm call failed model=%s error=%s after %.1fs", self.model, type(exc).__name__,
                            time.perf_counter() - t0)
                raise LLMUnavailable(type(exc).__name__) from exc
            log.info("llm call ok model=%s in %.1fs", self.model, time.perf_counter() - t0)
        return _THINK_BLOCK.sub("", content).strip()
