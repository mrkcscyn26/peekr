"""T-06: C10 query parser (FR-11). Today is fixed; local time zone is whatever the laptop uses."""

from datetime import date, datetime, timezone

import pytest

from app.search.hybrid import fts_query, make_snippet
from app.search.query_parser import parse

TODAY = date(2026, 10, 9)  # a Friday


def local_day(iso: str) -> date:
    return datetime.fromisoformat(iso).astimezone().date()


@pytest.mark.parametrize("q,start,end", [
    ("bill last month", date(2026, 9, 1), date(2026, 10, 1)),
    ("resibo noong nakaraang buwan", date(2026, 9, 1), date(2026, 10, 1)),
    ("thesis kahapon", date(2026, 10, 8), date(2026, 10, 9)),
    ("notes ngayon", date(2026, 10, 9), date(2026, 10, 10)),
    ("memo ngayong linggo", date(2026, 10, 5), date(2026, 10, 12)),
    ("memo noong isang linggo", date(2026, 9, 28), date(2026, 10, 5)),
    ("slides noong Marso", date(2026, 3, 1), date(2026, 4, 1)),
    ("report Disyembre", date(2025, 12, 1), date(2026, 1, 1)),
    ("report January 2025", date(2025, 1, 1), date(2025, 2, 1)),
    ("lease 3 days ago", date(2026, 10, 6), date(2026, 10, 7)),
    ("bill 12 March 2026", date(2026, 3, 12), date(2026, 3, 13)),
    ("assignment sa may 2026", date(2026, 5, 1), date(2026, 6, 1)),
])
def test_dates(q, start, end):
    p = parse(q, TODAY)
    assert (local_day(p.date_from), local_day(p.date_to)) == (start, end)
    assert datetime.fromisoformat(p.date_from).tzinfo == timezone.utc


def test_may_as_filipino_word_is_not_a_month():
    p = parse("may assignment ba ako", TODAY)
    assert p.date_from is None and p.semantic_text == "may assignment ba ako"


def test_file_type_folder_and_semantic_text():
    p = parse("pdf sa Downloads tungkol sa passport", TODAY)
    assert p.extensions == [".pdf"] and p.folder_hint == "downloads"
    assert p.semantic_text == "tungkol sa passport"
    p = parse("slides tungkol sa photosynthesis", TODAY)
    assert p.extensions == [".pptx"]
    p = parse("word files in the school folder", TODAY)
    assert p.extensions == [".docx"] and p.folder_hint == "school" and p.semantic_text == ""
    assert parse("yung pdf last month", TODAY).semantic_text == ""
    assert parse("tungkol sa school", TODAY).folder_hint is None  # 'sa' alone is not a folder clue


def test_fts_query_escapes_and_snippet_centers():
    assert fts_query('e-wallet "AND" OR*') == '"wallet" OR "and" OR "or"'  # 1-char terms dropped, all quoted
    text = "x " * 300 + "Meralco total due here " + "y " * 300
    s = make_snippet(text, ["meralco"], 80)
    assert "Meralco" in s and len(s) <= 86
