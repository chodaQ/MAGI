"""Entry point for scanning a source tree and producing an AnalysisResult."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Set

from . import c_analyzer, python_analyzer
from .result import AnalysisResult

DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env",
    "node_modules", "build", "dist", ".tox", ".mypy_cache", ".pytest_cache",
    ".eggs", "target",
}


def _walk_files(root: Path, ignore_dirs: Set[str]) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in ignore_dirs for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def analyze_path(
    root: Path,
    ignore_dirs: Optional[Set[str]] = None,
) -> AnalysisResult:
    """Scan every supported source file under ``root``.

    ``root`` may be a single file or a directory tree. Returns an
    :class:`AnalysisResult` aggregating evidence from every file that
    matched a supported language.
    """
    root = Path(root)
    ignore = DEFAULT_IGNORE_DIRS if ignore_dirs is None else ignore_dirs
    result = AnalysisResult()

    for path in _walk_files(root, ignore):
        if path.suffix in c_analyzer.C_SUFFIXES:
            result.evidence.extend(c_analyzer.scan_file(path))
            result.files_scanned += 1
        elif path.suffix in python_analyzer.PY_SUFFIXES:
            result.evidence.extend(python_analyzer.scan_file(path))
            result.files_scanned += 1
        else:
            result.files_skipped += 1

    return result
