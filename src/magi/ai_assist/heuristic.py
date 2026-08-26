"""Default, always-available resolver: no ML, no dependencies.

Currently implements one concrete disambiguation rule that matters in
practice: if a C source file *defines* a function with the same name
as a matched libc/syscall call (e.g. the project has its own
``static int open(const char *path, ...)`` helper), the match almost
certainly does not indicate real kernel capability usage, so it is
dropped.

This is the resolver used when no heavier local model is configured,
and it is what "Phase 1 보조 (기본 내장)" refers to in the README.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

from ..analyzer.c_analyzer import C_SUFFIXES
from ..analyzer.patterns import CAPABILITIES
from ..analyzer.result import AnalysisResult
from .base import Resolver

_ALL_C_CALLS = frozenset().union(*(cap.c_calls for cap in CAPABILITIES.values()))


def _looks_like_local_definition(text: str, name: str) -> bool:
    # e.g. "static int open(const char *path, int flags) {" or
    # "void fork(void)\n{" -- return type + name + (...) + { , allowing
    # the brace on the same or next non-comment line.
    pattern = re.compile(
        r"^[ \t]*[A-Za-z_][\w\s\*]*?\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*"
        r"(\{|$)",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        if m.group(1) == "{":
            return True
        # Brace on the following line (common K&R style).
        tail = text[m.end():m.end() + 20].lstrip()
        if tail.startswith("{"):
            return True
    return False


class HeuristicResolver(Resolver):
    name = "heuristic"

    def is_available(self) -> bool:
        return True

    def refine(self, result: AnalysisResult) -> AnalysisResult:
        file_cache: Dict[str, str] = {}
        kept = []
        dropped = []

        for ev in result.evidence:
            eligible = (
                ev.kind == "call"
                and ev.matched in _ALL_C_CALLS
                and ev.source.endswith(tuple(C_SUFFIXES))
            )
            if eligible:
                if ev.source not in file_cache:
                    try:
                        file_cache[ev.source] = Path(ev.source).read_text(
                            encoding="utf-8", errors="replace"
                        )
                    except OSError:
                        file_cache[ev.source] = ""
                if _looks_like_local_definition(file_cache[ev.source], ev.matched):
                    dropped.append(ev)
                    continue
            kept.append(ev)

        refined = AnalysisResult(
            evidence=kept,
            files_scanned=result.files_scanned,
            files_skipped=result.files_skipped,
        )
        refined.dropped_as_local_shadow = dropped  # type: ignore[attr-defined]
        return refined
