"""C10 Query parser. Implements F3. Covers FR-9, FR-11. Built in T-06.

Rules only (no LLM unless search.query_llm_fallback is true, not implemented in the MVP).
Extracts file type, date range and folder hint; semantic_text is the query with the
clue words removed (Section 8.10). Dates use the laptop's local time zone and are
returned as UTC ISO strings; date_to is exclusive.

Assumptions (flagged):
- English 'may' is only read as the month when it has a year or follows in/noong/nung/sa/last,
  because 'may' is a common Filipino word ("there is").
- A folder hint needs the word 'folder' after the name (sa school folder, in the Work folder) or
  one of the standard Windows folders (Downloads, Documents, Desktop, Pictures).
- 'document' maps to .docx as Section 8.10 lists it with word and docx.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import dateparser

FILE_TYPES: list[tuple[str, str]] = [
    (r"text\s+files?|txt", ".txt"),
    (r"pdfs?", ".pdf"),
    (r"powerpoints?|pptx?|slides?|presentations?", ".pptx"),
    (r"word(?:\s+files?|\s+docs?)?|docx?|documents?", ".docx"),
]

MONTHS = {
    "january": 1, "enero": 1, "february": 2, "pebrero": 2, "march": 3, "marso": 3, "april": 4, "abril": 4,
    "mayo": 5, "june": 6, "hunyo": 6, "july": 7, "hulyo": 7, "august": 8, "agosto": 8,
    "september": 9, "setyembre": 9, "october": 10, "oktubre": 10, "november": 11, "nobyembre": 11,
    "december": 12, "disyembre": 12,
}
_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

RELATIVE: list[tuple[str, str]] = [
    (r"noong\s+nakaraang\s+buwan|nung\s+nakaraang\s+buwan|nakaraang\s+buwan|last\s+month", "last_month"),
    (r"noong\s+isang\s+linggo|nung\s+isang\s+linggo|nakaraang\s+linggo|last\s+week", "last_week"),
    (r"noong\s+isang\s+taon|nung\s+isang\s+taon|nakaraang\s+taon|last\s+year", "last_year"),
    (r"ngayong\s+linggo|this\s+week", "this_week"),
    (r"ngayong\s+buwan|this\s+month", "this_month"),
    (r"ngayong\s+taon|this\s+year", "this_year"),
    (r"kahapon|yesterday", "yesterday"),
    (r"ngayong\s+araw|ngayon|today", "today"),
]

STANDARD_FOLDERS = r"downloads|documents|desktop|pictures"
FOLDER_PATTERNS = [
    re.compile(r"\b(?:in|sa|from|nasa|galing\s+sa)\s+(?:the\s+|ang\s+|my\s+)?([\w\-]+)\s+folder\b", re.I),
    re.compile(rf"\b(?:in|sa|from|nasa|galing\s+sa)\s+(?:the\s+|my\s+)?({STANDARD_FOLDERS})\b", re.I),
]

EXPLICIT_DATE = re.compile(
    rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}"
    rf"|\d{{1,2}}\s+(?:{_MONTH_RE}|may)\s*,?\s+\d{{4}}"
    rf"|(?:{_MONTH_RE}|may)\s+\d{{1,2}}\s*,?\s+\d{{4}})\b", re.I)
MONTH_YEAR = re.compile(rf"\b(?:(?:in|noong|nung|sa|of|last)\s+)?({_MONTH_RE})(?:\s+(\d{{4}}))?\b", re.I)
MAY_MONTH = re.compile(r"\b(?:(?:in|noong|nung|sa|of|last)\s+may(?:\s+(\d{4}))?|may\s+(\d{4}))\b", re.I)
DAYS_AGO = re.compile(r"\b(\d{1,3})\s+(?:days?\s+ago|araw\s+na\s+ang\s+nakalipas|araw\s+na\s+nakalipas)\b", re.I)

# Words that carry no meaning on their own; if only these remain, semantic_text is empty.
FILLER = {
    "file", "files", "yung", "ang", "mga", "the", "my", "ko", "a", "an", "all", "show", "find", "hanapin",
    "pakita", "ipakita", "me", "na", "ng", "from", "sa", "in", "noong", "nung", "of", "and", "at", "o", "or",
    "lahat", "list", "open", "get", "akin", "aking", "ba", "po", "yun", "iyong", "nasaan", "where", "is",
}


@dataclass
class ParsedQuery:
    query: str
    semantic_text: str
    extensions: list[str] = field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    folder_hint: str | None = None

    def as_dict(self) -> dict:
        return {"extensions": self.extensions, "date_from": self.date_from, "date_to": self.date_to,
                "folder_hint": self.folder_hint}


def _local_tz():
    return datetime.now().astimezone().tzinfo


def _range(start: date, end: date) -> tuple[str, str]:
    tz = _local_tz()
    s = datetime.combine(start, time.min, tz).astimezone(timezone.utc)
    e = datetime.combine(end, time.min, tz).astimezone(timezone.utc)
    return s.isoformat(timespec="seconds"), e.isoformat(timespec="seconds")


def _month_range(year: int, month: int) -> tuple[str, str]:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return _range(date(year, month, 1), nxt)


def _relative(kind: str, today: date) -> tuple[str, str]:
    monday = today - timedelta(days=today.weekday())
    first = today.replace(day=1)
    if kind == "today":
        return _range(today, today + timedelta(days=1))
    if kind == "yesterday":
        return _range(today - timedelta(days=1), today)
    if kind == "this_week":
        return _range(monday, monday + timedelta(days=7))
    if kind == "last_week":
        return _range(monday - timedelta(days=7), monday)
    if kind == "this_month":
        return _month_range(today.year, today.month)
    if kind == "last_month":
        prev = first - timedelta(days=1)
        return _month_range(prev.year, prev.month)
    if kind == "this_year":
        return _range(date(today.year, 1, 1), date(today.year + 1, 1, 1))
    if kind == "last_year":
        return _range(date(today.year - 1, 1, 1), date(today.year, 1, 1))
    raise ValueError(kind)


def _month_without_year(month: int, today: date) -> int:
    return today.year if month <= today.month else today.year - 1


def parse(query: str, today: date | None = None) -> ParsedQuery:
    today = today or datetime.now().date()
    text = f" {query.strip()} "
    pq = ParsedQuery(query=query, semantic_text="")

    def cut(m: re.Match) -> None:
        nonlocal text
        text = text[: m.start()] + " " + text[m.end():]

    # Folder hint first, so a folder name is not read as a file type or date.
    for pat in FOLDER_PATTERNS:
        m = pat.search(text)
        if m:
            pq.folder_hint = m.group(1).lower()
            cut(m)
            break

    # Dates: explicit dates, then N days ago, relative phrases, month names.
    m = EXPLICIT_DATE.search(text)
    if m:
        d = dateparser.parse(m.group(0), languages=["en", "tl"], settings={"PREFER_DAY_OF_MONTH": "first"})
        if d:
            pq.date_from, pq.date_to = _range(d.date(), d.date() + timedelta(days=1))
            cut(m)
    if pq.date_from is None and (m := DAYS_AGO.search(text)):
        day = today - timedelta(days=int(m.group(1)))
        pq.date_from, pq.date_to = _range(day, day + timedelta(days=1))
        cut(m)
    if pq.date_from is None:
        for pat, kind in RELATIVE:
            m = re.search(rf"\b(?:{pat})\b", text, re.I)
            if m:
                pq.date_from, pq.date_to = _relative(kind, today)
                cut(m)
                break
    if pq.date_from is None and (m := MONTH_YEAR.search(text)):
        month = MONTHS[m.group(1).lower()]
        year = int(m.group(2)) if m.group(2) else _month_without_year(month, today)
        pq.date_from, pq.date_to = _month_range(year, month)
        cut(m)
    if pq.date_from is None and (m := MAY_MONTH.search(text)):
        y = m.group(1) or m.group(2)
        year = int(y) if y else _month_without_year(5, today)
        pq.date_from, pq.date_to = _month_range(year, 5)
        cut(m)

    for pat, ext in FILE_TYPES:
        for m in list(re.finditer(rf"\b(?:{pat})\b", text, re.I))[::-1]:
            if ext not in pq.extensions:
                pq.extensions.append(ext)
            cut(m)

    semantic = re.sub(r"\s+", " ", text).strip(" ,.?!")
    words = re.findall(r"\w+", semantic.lower())
    pq.semantic_text = "" if all(w in FILLER for w in words) else semantic
    return pq
