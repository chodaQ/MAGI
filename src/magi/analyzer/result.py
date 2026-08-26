"""Shared result types for the analyzer package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass(frozen=True)
class Evidence:
    """One concrete match: this file/line indicates this capability."""

    capability: str
    source: str
    line: int
    snippet: str
    matched: str
    kind: str = "call"  # "call" (function invocation) or "token" (literal/macro)


@dataclass
class AnalysisResult:
    evidence: List[Evidence] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0

    @property
    def capabilities(self) -> Set[str]:
        return {e.capability for e in self.evidence}

    def evidence_for(self, capability: str) -> List[Evidence]:
        return [e for e in self.evidence if e.capability == capability]

    def by_capability(self) -> Dict[str, List[Evidence]]:
        out: Dict[str, List[Evidence]] = {}
        for e in self.evidence:
            out.setdefault(e.capability, []).append(e)
        return out

    def merge(self, other: "AnalysisResult") -> None:
        self.evidence.extend(other.evidence)
        self.files_scanned += other.files_scanned
        self.files_skipped += other.files_skipped
