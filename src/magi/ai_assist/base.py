"""Interface for pluggable ambiguous-evidence resolvers.

The rule-based analyzer (:mod:`magi.analyzer`) is intentionally naive:
it flags any identifier matching a known API name, even if that
identifier is actually a locally-defined function that just happens to
share a name with a libc/syscall wrapper (e.g. a project defining its
own ``open()`` helper). A resolver's job is to look at that raw
evidence plus the surrounding source and decide what to keep.

Every resolver must work with zero network access and zero required
external services -- that is a hard project invariant, not a
suggestion (see README, "AI 보조 분석"). Implementations that need an
optional heavier local model (e.g. a GGUF model via llama-cpp-python)
must fail closed: if the dependency or model file is unavailable,
`is_available()` returns False and callers fall back to the next
resolver in the chain.
"""

from __future__ import annotations

import abc
from pathlib import Path

from ..analyzer.result import AnalysisResult


class Resolver(abc.ABC):
    name: str = "resolver"

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if this resolver can actually run right now."""

    @abc.abstractmethod
    def refine(self, result: AnalysisResult) -> AnalysisResult:
        """Return a new AnalysisResult with low-confidence evidence
        either dropped (false positive) or kept (confirmed)."""
