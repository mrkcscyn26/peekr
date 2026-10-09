"""C18 OS actions. Implements F2, F7. Covers FR-1, FR-13. Built in T-07.

Native folder dialog (tkinter, run in a child process so it never blocks or crashes the
server thread), open a file with its default app, show a file in Explorer.
These only open or show files; nothing is written, moved or deleted (FR-3).
"""

from __future__ import annotations

import os
import subprocess
import sys

_PICK_SCRIPT = (
    "import tkinter as tk\n"
    "from tkinter import filedialog\n"
    "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
    "p = filedialog.askdirectory(title='Choose a folder for Peekr to index', mustexist=True)\n"
    "print(p or '')\n"
)


class OsActionError(RuntimeError):
    pass


def pick_folder(timeout: float = 600) -> str | None:
    try:
        out = subprocess.run([sys.executable, "-c", _PICK_SCRIPT], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OsActionError(f"folder dialog failed: {type(exc).__name__}") from exc
    path = out.stdout.strip()
    return os.path.normpath(path) if path else None


def open_file(path: str) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 - opens with the default application
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as exc:
        raise OsActionError(str(exc)) from exc


def open_folder(path: str) -> None:
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except OSError as exc:
        raise OsActionError(str(exc)) from exc
