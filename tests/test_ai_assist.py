from pathlib import Path

from magi.ai_assist import HeuristicResolver, LocalLLMResolver, get_resolver_chain
from magi.analyzer import analyze_path

FIXTURES = Path(__file__).parent / "fixtures" / "c_project" / "src"


def test_heuristic_drops_locally_shadowed_function():
    result = analyze_path(FIXTURES / "shadow.c")
    matched_open = [e for e in result.evidence if e.matched == "open"]
    assert matched_open, "test setup: shadow.c should trigger a raw 'open' match"

    refined = HeuristicResolver().refine(result)
    assert all(e.matched != "open" for e in refined.evidence)


def test_heuristic_keeps_genuine_matches():
    result = analyze_path(FIXTURES / "server.c")
    refined = HeuristicResolver().refine(result)
    assert any(e.matched == "socket" for e in refined.evidence)


def test_llm_resolver_unavailable_without_model():
    resolver = LocalLLMResolver(model_path=None)
    assert resolver.is_available() is False


def test_llm_resolver_refine_is_noop_when_unavailable():
    result = analyze_path(FIXTURES / "server.c")
    resolver = LocalLLMResolver(model_path="/nonexistent/model.gguf")
    refined = resolver.refine(result)
    assert refined.evidence == result.evidence


def test_default_chain_excludes_llm_when_no_model_configured():
    chain = get_resolver_chain()
    names = [r.name for r in chain]
    assert names == ["heuristic"]
