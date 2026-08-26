"""Static analysis for C/C++ source files.

This is a lightweight lexical analyzer, not a full C parser: it strips
comments, then looks for (a) bare identifiers immediately followed by
``(`` as evidence of a function call, and (b) known literal/macro
tokens anywhere in the file. That is enough to reliably detect use of
libc/syscall wrappers (``socket()``, ``fork()``, ``mmap()``, ...)
without needing a full compiler front-end, at the cost of not
understanding scope (a local function that happens to be named
``open`` would also match). This tradeoff is documented in the
project README.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List

from .patterns import CAPABILITIES
from .result import Evidence

_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_LINE_COMMENT_RE = re.compile(r"//.*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

C_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"}


def _strip_comments(text: str) -> str:
    text = _BLOCK_COMMENT_RE.sub(" ", text)
    text = _LINE_COMMENT_RE.sub(" ", text)
    return text


def scan_text(text: str, source_name: str) -> List[Evidence]:
    """Scan raw C source text and return capability evidence found."""
    evidence: List[Evidence] = []
    stripped = _strip_comments(text)
    lines = stripped.splitlines()

    calls_by_line = []
    for lineno, line in enumerate(lines, start=1):
        for m in _CALL_RE.finditer(line):
            calls_by_line.append((lineno, m.group(1)))

    for cap in CAPABILITIES.values():
        for lineno, name in calls_by_line:
            if name in cap.c_calls:
                evidence.append(
                    Evidence(
                        capability=cap.id,
                        source=source_name,
                        line=lineno,
                        snippet=lines[lineno - 1].strip()[:120],
                        matched=name,
                        kind="call",
                    )
                )
        if cap.c_tokens:
            for lineno, line in enumerate(lines, start=1):
                for token in cap.c_tokens:
                    if token in line:
                        evidence.append(
                            Evidence(
                                capability=cap.id,
                                source=source_name,
                                line=lineno,
                                snippet=line.strip()[:120],
                                matched=token,
                                kind="token",
                            )
                        )
    return evidence


def scan_file(path: Path) -> List[Evidence]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(text, str(path))


def iter_c_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix in C_SUFFIXES:
            yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in C_SUFFIXES:
            yield path
