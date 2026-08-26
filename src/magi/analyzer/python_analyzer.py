"""Static analysis for Python source files, using the ``ast`` module.

Unlike the C analyzer this one understands scope well enough to
resolve simple import aliases (``import os as _os; _os.fork()`` is
still recognized as ``os.fork``), which keeps the false-positive rate
much lower than plain text search.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Optional

from .patterns import CAPABILITIES
from .result import Evidence

PY_SUFFIXES = {".py"}

# Build a reverse index: dotted call name -> capability id, once.
_CALL_INDEX = {}
for _cap in CAPABILITIES.values():
    for _name in _cap.python_calls:
        _CALL_INDEX.setdefault(_name, []).append(_cap.id)


class _ImportTracker(ast.NodeVisitor):
    """Resolves ``ast.Call`` nodes to dotted names, following aliases."""

    def __init__(self, source_name: str, lines: List[str]):
        self.source_name = source_name
        self.lines = lines
        self.aliases = {}  # local name -> real dotted module/name
        self.evidence: List[Evidence] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            self.aliases[local] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            self.aliases[local] = f"{module}.{alias.name}" if module else alias.name
        self.generic_visit(node)

    def _resolve(self, node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = self._resolve(node.value)
            if base is None:
                return None
            return f"{base}.{node.attr}"
        return None

    def visit_Call(self, node: ast.Call) -> None:
        dotted = self._resolve(node.func)
        candidates = set()
        if dotted:
            candidates.add(dotted)
            # Also try with the alias root replaced by its resolved form
            # already handled by _resolve. Additionally try just the
            # last 1-2 segments in case of deep re-exports.
            parts = dotted.split(".")
            if len(parts) >= 2:
                candidates.add(".".join(parts[-2:]))
        elif isinstance(node.func, ast.Name):
            candidates.add(node.func.id)

        for candidate in candidates:
            for cap_id in _CALL_INDEX.get(candidate, []):
                lineno = getattr(node, "lineno", 1)
                snippet = self.lines[lineno - 1].strip()[:120] if lineno - 1 < len(self.lines) else ""
                self.evidence.append(
                    Evidence(
                        capability=cap_id,
                        source=self.source_name,
                        line=lineno,
                        snippet=snippet,
                        matched=candidate,
                    )
                )
        self.generic_visit(node)


def scan_text(text: str, source_name: str) -> List[Evidence]:
    try:
        tree = ast.parse(text, filename=source_name)
    except SyntaxError:
        return []
    tracker = _ImportTracker(source_name, text.splitlines())
    tracker.visit(tree)
    return tracker.evidence


def scan_file(path: Path) -> List[Evidence]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(text, str(path))


def iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix in PY_SUFFIXES:
            yield root
        return
    for path in sorted(root.rglob("*.py")):
        if path.is_file():
            yield path
