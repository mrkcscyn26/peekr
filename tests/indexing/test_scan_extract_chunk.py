"""T-03 / T-04: C4 scanner, C5 extractors, C6 chunker (FR-4, FR-5)."""

import os

import pytest

from app.core.config import load_config
from app.indexing.chunker import chunk_segments
from app.indexing.extractors import ExtractError, Segment, extract
from app.indexing.extractors.txt import decode
from app.indexing.scanner import scan
from make_demo_data import BAD_FILES, DOCS, IGNORED_FILES

CFG = load_config()


def test_scanner_filters_temp_hidden_unsupported_and_excluded(demo_src):
    names = {e.name for e in scan(str(demo_src), CFG.indexing)}
    assert len(names) == len(DOCS) + len(BAD_FILES)
    assert not names & set(IGNORED_FILES)
    excluded = {e.name for e in scan(str(demo_src), CFG.indexing, [str(demo_src / "Downloads")])}
    assert "scan_0012.pdf" not in excluded and "adobong_manok.txt" in excluded


def test_every_demo_document_extracts_with_locations(demo_src):
    for rel, *_ in DOCS:
        segs = extract(str(demo_src / rel))
        assert segs and all(s.text for s in segs), rel
        prefix = {".pdf": "page ", ".pptx": "slide ", ".docx": "part ", ".txt": "part "}[os.path.splitext(rel)[1]]
        assert all(s.location.startswith(prefix) for s in segs), rel


def test_multi_page_pdf_and_pptx_notes(demo_src):
    segs = extract(str(demo_src / "Work/employee_handbook_leave_policy.pdf"))
    assert [s.location for s in segs] == ["page 1", "page 2", "page 3"]
    assert "Maternity" in segs[1].text
    slides = extract(str(demo_src / "School/Biology/photosynthesis_lesson.pptx"))
    assert "Quiz next meeting" in slides[3].text  # speaker notes


@pytest.mark.parametrize("name,reason", sorted(BAD_FILES.items()))
def test_bad_files_get_reason_codes(demo_src, name, reason):
    with pytest.raises(ExtractError) as err:
        extract(str(demo_src / "Bad" / name))
    assert err.value.reason == reason


def test_txt_encodings():
    assert decode("Señor".encode("cp1252")) == "Señor"
    assert decode("\ufeffhello".encode("utf-8")) == "hello"


def test_chunker_rules():
    ch = CFG.chunking
    long = " ".join(f"Sentence number {i} talks about budgets and bills." for i in range(120))
    chunks = chunk_segments([Segment("short page", "page 1"), Segment(long, "page 2"), Segment("  ", "page 3")], ch)
    assert chunks[0].text == "short page" and chunks[0].location == "page 1"
    assert [c.index for c in chunks] == list(range(len(chunks)))
    rest = chunks[1:]
    assert len(rest) > 3 and all(c.location == "page 2" for c in rest)
    assert all(c.text.strip() for c in chunks)
    assert all(len(c.text) <= ch.target_chars + ch.min_chunk_chars for c in rest)
    # overlap: the start of each next chunk repeats the end of the previous one
    assert rest[1].text[:40] in rest[0].text
