from ..analyzer.result import AnalysisResult
from .base import Resolver
from .heuristic import HeuristicResolver
from .llm import LocalLLMResolver

__all__ = [
    "Resolver", "HeuristicResolver", "LocalLLMResolver",
    "get_resolver_chain", "refine",
]


def get_resolver_chain(model_path=None):
    """Build the resolver chain: always-on heuristic first, then the
    optional local LLM on top if (and only if) it is actually usable."""
    chain = [HeuristicResolver()]
    llm = LocalLLMResolver(model_path=model_path)
    if llm.is_available():
        chain.append(llm)
    return chain


def refine(result: AnalysisResult, model_path=None) -> AnalysisResult:
    for resolver in get_resolver_chain(model_path=model_path):
        result = resolver.refine(result)
    return result
