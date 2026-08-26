"""Optional local-LLM-backed resolver (Phase "2단계 보조").

Not bundled: MAGI ships zero model weights (they would bloat the
package by hundreds of MB to multiple GB and every project's hardware
budget differs). This module defines the integration point so a user
with enough local hardware can plug in any GGUF model via
``llama-cpp-python``. If the dependency or model file isn't present,
``is_available()`` returns False and the caller (see
:func:`magi.ai_assist.get_resolver_chain`) silently falls back to the
zero-dependency :class:`~magi.ai_assist.heuristic.HeuristicResolver`,
which is always active. The core pipeline never depends on this
module succeeding.
"""

from __future__ import annotations

import os
from typing import Optional

from ..analyzer.result import AnalysisResult, Evidence
from .base import Resolver

_PROMPT_TEMPLATE = """You review static-analysis matches for a Linux kernel \
capability detector. Given a code snippet and a claimed API call, answer \
with exactly one word: YES if the snippet is a genuine use of the named \
system/library call, NO if it is unrelated (e.g. a local variable, a \
locally-defined function of the same name, a comment, or unrelated \
identifier).

API: {api}
Snippet: {snippet}
Answer:"""


class LocalLLMResolver(Resolver):
    name = "local-llm"

    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 512):
        self.model_path = model_path or os.environ.get("MAGI_LLM_MODEL_PATH")
        self.n_ctx = n_ctx
        self._llm = None

    def is_available(self) -> bool:
        if not self.model_path or not os.path.isfile(self.model_path):
            return False
        try:
            import llama_cpp  # noqa: F401
        except ImportError:
            return False
        return True

    def _load(self):
        if self._llm is None:
            from llama_cpp import Llama

            self._llm = Llama(model_path=self.model_path, n_ctx=self.n_ctx, verbose=False)
        return self._llm

    def _confirm(self, ev: Evidence) -> bool:
        llm = self._load()
        prompt = _PROMPT_TEMPLATE.format(api=ev.matched, snippet=ev.snippet)
        out = llm(prompt, max_tokens=3, temperature=0.0)
        text = out["choices"][0]["text"].strip().upper()
        return text.startswith("Y")

    def refine(self, result: AnalysisResult) -> AnalysisResult:
        if not self.is_available():
            return result

        kept = []
        for ev in result.evidence:
            try:
                if self._confirm(ev):
                    kept.append(ev)
            except Exception:
                # Fail closed on any model error: keep the rule-based
                # match rather than silently losing evidence.
                kept.append(ev)

        return AnalysisResult(
            evidence=kept,
            files_scanned=result.files_scanned,
            files_skipped=result.files_skipped,
        )
