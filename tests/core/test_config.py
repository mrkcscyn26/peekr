"""T-01: C3 configuration rules (FR-24, hard rule 4)."""

import pytest

from app.core.config import ConfigError, is_within, load_config


def test_defaults_load_and_create_data_dirs(tmp_path):
    cfg = load_config(overrides={"data_dir": str(tmp_path / "d")})
    assert cfg.server.host == "127.0.0.1"
    assert cfg.db_path.parent.is_dir() and cfg.logs_path.is_dir()
    assert cfg.embedding.device == "cpu"


@pytest.mark.parametrize("key,value", [
    ("server.host", "0.0.0.0"),
    ("ollama.url", "http://example.com:11434"),
    ("llm.model", "gpt-oss:120b-cloud"),
    ("llm.model", "qwen3:cloud"),
])
def test_hard_rules_rejected(tmp_path, key, value):
    with pytest.raises(ConfigError):
        load_config(overrides={"data_dir": str(tmp_path), key: value})


def test_is_within_case_insensitive_and_no_prefix_confusion():
    assert is_within(r"C:\Docs\School\a.pdf", r"c:\docs")
    assert not is_within(r"C:\DocsOld\a.pdf", r"C:\Docs")
